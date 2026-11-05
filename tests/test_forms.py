"""The Forms plugin: building a form, answering it, results and CSV.

Runs with Hubra's fixtures once the plugin is in plugins/forms of a Hubra
checkout (see README.md).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/forms"

FIELDS = [
    {"kind": "text", "label": "Name des Kindes", "required": True},
    {
        "kind": "choice",
        "label": "T-Shirt",
        "options": ["S", "M", "L"],
        "required": True,
    },
    {
        "kind": "multi",
        "label": "Essen",
        "options": ["Vegi", "Ohne Nüsse", "Laktosefrei"],
    },
    {"kind": "number", "label": "Alter"},
    {"kind": "yesno", "label": "Fotos erlaubt"},
    {"kind": "date", "label": "Anreise"},
]


@pytest.fixture
def club(client, app, db, seeded_db):
    """Bea builds forms; Max and Lea are in the Jugend group; Ola isn't."""
    from hubra.core.models.group import Group, GroupMembership

    set_modules(True, "forms")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    bea = _make_role_and_member(
        db, tier, name="Bea", permission_keys=["forms.forms.update"]
    )
    ids = {"bea": bea.id}
    for name in ("Max", "Lea", "Ola"):
        ids[name.lower()] = _make_role_and_member(db, tier, name=name).id
    group = Group(name="Jugend")
    db.session.add(group)
    db.session.flush()
    for m in ("max", "lea"):
        db.session.add(GroupMembership(group_id=group.id, member_id=ids[m]))
    db.session.commit()
    ids["group"] = group.id
    return ids


def _make(client, **extra):
    body = {"title": "Lager 2027", "fields": FIELDS, **extra}
    made = client.post(f"{BASE}/forms", json=body)
    assert made.status_code == 201, made.get_json()
    return made.get_json()


def test_build_open_answer_and_results(client, db, club):
    from hubra.core.models.notification import Notification

    _login(client, "max@test.ch")
    assert (
        client.post(f"{BASE}/forms", json={"title": "x", "fields": FIELDS}).status_code
        == 403
    )

    _login(client, "bea@test.ch")
    bad = client.post(
        f"{BASE}/forms",
        json={
            "title": "x",
            "fields": [{"kind": "choice", "label": "A", "options": ["1"]}],
        },
    )
    assert bad.status_code == 400
    form = _make(client, groupId=club["group"], resultsPublic=True)
    assert form["state"] == "draft" and [f["kind"] for f in form["fields"]][:2] == [
        "text",
        "choice",
    ]

    # Drafts stay hidden from members.
    _login(client, "max@test.ch")
    assert client.get(f"{BASE}/forms/{form['id']}").status_code == 404

    _login(client, "bea@test.ch")
    opened = client.post(
        f"{BASE}/forms/{form['id']}/status", json={"status": "open", "announce": True}
    )
    assert opened.get_json()["announced"] == 2
    told = db.session.query(Notification).filter(
        Notification.link == f"/app/forms/{form['id']}"
    )
    assert {n.member_id for n in told} == {club["max"], club["lea"]}

    _login(client, "ola@test.ch")
    assert client.get(f"{BASE}/forms").get_json() == []
    assert (
        client.put(
            f"{BASE}/forms/{form['id']}/response", json={"answers": {}}
        ).status_code
        == 404
    )

    _login(client, "max@test.ch")
    f = {x["label"]: str(x["id"]) for x in form["fields"]}
    missing = client.put(
        f"{BASE}/forms/{form['id']}/response", json={"answers": {f["T-Shirt"]: "M"}}
    )
    assert missing.status_code == 400 and missing.get_json()["fieldId"] == int(
        f["Name des Kindes"]
    )
    wrong = client.put(
        f"{BASE}/forms/{form['id']}/response",
        json={"answers": {f["Name des Kindes"]: "Tim", f["T-Shirt"]: "XXL"}},
    )
    assert wrong.status_code == 400
    done = client.put(
        f"{BASE}/forms/{form['id']}/response",
        json={
            "answers": {
                f["Name des Kindes"]: " Tim ",
                f["T-Shirt"]: "M",
                f["Essen"]: ["Laktosefrei", "Vegi"],
                f["Alter"]: "11",
                f["Fotos erlaubt"]: True,
                f["Anreise"]: "2027-07-10",
            }
        },
    ).get_json()
    assert done["myAnswers"][f["Name des Kindes"]] == "Tim"
    assert done["myAnswers"][f["Essen"]] == ["Vegi", "Laktosefrei"]
    assert done["myAnswers"][f["Alter"]] == 11
    # Results are public once answered: counts, no free text.
    res = client.get(f"{BASE}/forms/{form['id']}/results").get_json()
    shirt = next(s for s in res["summary"] if s["label"] == "T-Shirt")
    assert {c["option"]: c["count"] for c in shirt["counts"]} == {
        "S": 0,
        "M": 1,
        "L": 0,
    }
    assert "rows" not in res and all("values" not in s for s in res["summary"])

    _login(client, "lea@test.ch")
    assert client.get(f"{BASE}/forms/{form['id']}/results").status_code == 403
    client.put(
        f"{BASE}/forms/{form['id']}/response",
        json={
            "answers": {
                f["Name des Kindes"]: "=HYPERLINK(1)",
                f["T-Shirt"]: "S",
                f["Alter"]: 13,
            }
        },
    )

    _login(client, "bea@test.ch")
    res = client.get(f"{BASE}/forms/{form['id']}/results").get_json()
    assert res["responses"] == 2 and res["missing"] == []
    age = next(s for s in res["summary"] if s["label"] == "Alter")
    assert age["average"] == 12 and age["sum"] == 24
    assert {r["name"] for r in res["rows"]} == {"Test Max", "Test Lea"}
    csv = client.get(f"{BASE}/forms/{form['id']}/results.csv")
    text = csv.data.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Name;Beantwortet;Name des Kindes;T-Shirt")
    assert "'=HYPERLINK(1)" in text and "Vegi, Laktosefrei" in text and ";Ja;" in text

    # A field's kind is fixed once answered; answered forms don't go back to draft.
    changed = [dict(x) for x in done["fields"]]
    changed[3]["kind"] = "text"
    assert (
        client.put(
            f"{BASE}/forms/{form['id']}",
            json={"title": "Lager 2027", "fields": changed},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{BASE}/forms/{form['id']}/status", json={"status": "draft"}
        ).status_code
        == 409
    )

    # Closed: no more answers.
    client.post(f"{BASE}/forms/{form['id']}/status", json={"status": "closed"})
    _login(client, "max@test.ch")
    assert (
        client.put(
            f"{BASE}/forms/{form['id']}/response", json={"answers": {}}
        ).status_code
        == 409
    )


def test_anonymous_copy_and_reminder(app, client, db, club):
    from hubra.core.models.notification import Notification
    from hubra_forms import services
    from hubra_forms.models import FormsForm

    _login(client, "bea@test.ch")
    closes = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()
    form = _make(
        client,
        title="Umfrage",
        anonymous=True,
        remind=True,
        closesAt=closes,
        fields=[{"kind": "choice", "label": "Zufrieden?", "options": ["Ja", "Nein"]}],
    )
    client.post(f"{BASE}/forms/{form['id']}/status", json={"status": "open"})
    _login(client, "ola@test.ch")
    fid = str(form["fields"][0]["id"])
    client.put(f"{BASE}/forms/{form['id']}/response", json={"answers": {fid: "Ja"}})

    _login(client, "bea@test.ch")
    res = client.get(f"{BASE}/forms/{form['id']}/results").get_json()
    assert res["rows"][0]["name"] is None and "missing" not in res
    assert (
        client.get(f"{BASE}/forms/{form['id']}/results.csv")
        .data.decode("utf-8-sig")
        .startswith("Beantwortet;")
    )

    with app.test_request_context():
        assert services.remind() >= 3  # Bea, Max, Lea (and the seeded admin)
        assert services.remind() == 0
        db.session.commit()
    bells = db.session.query(Notification).filter(
        Notification.title == "Formular schliesst morgen"
    )
    assert club["ola"] not in {n.member_id for n in bells}

    copy = client.post(f"{BASE}/forms/{form['id']}/copy").get_json()
    assert (
        copy["state"] == "draft"
        and copy["title"] == "Umfrage (Kopie)"
        and len(copy["fields"]) == 1
    )
    assert client.delete(f"{BASE}/forms/{form['id']}").status_code == 204
    assert db.session.get(FormsForm, form["id"]) is None

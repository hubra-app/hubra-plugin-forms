"""Who a form is for, checking answers, the summary, and reminders."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from hubra.core.extensions import db
from hubra.core.models.group import GroupMembership
from hubra.core.models.member import Member

from .models import FormsField, FormsForm, FormsResponse
from .notify import notify

KINDS = ("text", "textarea", "number", "date", "choice", "multi", "yesno")
CHOICES = ("choice", "multi")
REMIND_BEFORE = timedelta(days=1)
# A form closes at most this far ahead, and its answers are deleted this long
# after it closed (revDSG: personal data only as long as needed).
MAX_OPEN = timedelta(days=366)
KEEP_ANSWERS = timedelta(days=365)


class BadAnswer(Exception):
    def __init__(self, field_id: int, message: str):
        super().__init__(message)
        self.field_id = field_id
        self.message = message


def now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_open(form: FormsForm) -> bool:
    closes = _aware(form.closes_at)
    return form.status == "open" and (closes is None or closes > now())


def state(form: FormsForm) -> str:
    """draft, open or closed (an open form past its date is closed)."""
    if form.status == "draft":
        return "draft"
    return "open" if is_open(form) else "closed"


def in_audience(member, form: FormsForm) -> bool:
    if member is None:
        return False
    if form.group_id is None:
        return True
    return (
        db.session.scalar(
            select(GroupMembership.id)
            .where(GroupMembership.group_id == form.group_id)
            .where(GroupMembership.member_id == member.id)
        )
        is not None
    )


def audience(form: FormsForm) -> list[int]:
    """The active members the form is for."""
    query = (
        select(Member.id)
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
    )
    if form.group_id is not None:
        query = query.join(
            GroupMembership, GroupMembership.member_id == Member.id
        ).where(GroupMembership.group_id == form.group_id)
    return list(db.session.scalars(query))


def fields(form_id: int) -> list[FormsField]:
    return list(
        db.session.scalars(
            select(FormsField)
            .where(FormsField.form_id == form_id)
            .order_by(FormsField.position, FormsField.id)
        )
    )


def clean(form_fields: list[FormsField], raw) -> dict[str, object]:
    """Checks a member's answers against the fields; returns what is kept."""
    if not isinstance(raw, dict):
        raise BadAnswer(0, "answers must be an object")
    out: dict[str, object] = {}
    for f in form_fields:
        value = raw.get(str(f.id))
        empty = value is None or value == "" or value == []
        if empty:
            if f.required:
                raise BadAnswer(f.id, f"{f.label}: an answer is needed")
            continue
        if f.kind in ("text", "textarea"):
            if not isinstance(value, str):
                raise BadAnswer(f.id, f"{f.label}: must be text")
            limit = 300 if f.kind == "text" else 5000
            value = value.strip()
            if len(value) > limit:
                raise BadAnswer(f.id, f"{f.label}: at most {limit} characters")
            if not value:
                if f.required:
                    raise BadAnswer(f.id, f"{f.label}: an answer is needed")
                continue
        elif f.kind == "number":
            if isinstance(value, bool):
                raise BadAnswer(f.id, f"{f.label}: must be a number")
            try:
                value = float(str(value).replace(",", ".").replace("'", ""))
            except ValueError:
                raise BadAnswer(f.id, f"{f.label}: must be a number") from None
            if abs(value) >= 1e12 or value != value:
                raise BadAnswer(f.id, f"{f.label}: must be a number")
            if value == int(value):
                value = int(value)
        elif f.kind == "date":
            try:
                value = date.fromisoformat(str(value)[:10]).isoformat()
            except ValueError:
                raise BadAnswer(f.id, f"{f.label}: must be a date") from None
        elif f.kind == "yesno":
            if not isinstance(value, bool):
                raise BadAnswer(f.id, f"{f.label}: must be yes or no")
        elif f.kind == "choice":
            if value not in (f.options or []):
                raise BadAnswer(f.id, f"{f.label}: not one of the choices")
        elif f.kind == "multi":
            if not isinstance(value, list) or any(
                v not in (f.options or []) for v in value
            ):
                raise BadAnswer(f.id, f"{f.label}: not one of the choices")
            # Keep the form's order, once each.
            value = [o for o in (f.options or []) if o in value]
        out[str(f.id)] = value
    return out


def responses(form_id: int) -> list[FormsResponse]:
    return list(
        db.session.scalars(
            select(FormsResponse)
            .where(FormsResponse.form_id == form_id)
            .order_by(FormsResponse.created_at, FormsResponse.id)
        )
    )


def summary(form_fields: list[FormsField], rows: list[FormsResponse]) -> list[dict]:
    """Per field: counts for choices and yes/no, sum and average for numbers,
    the answers themselves for text."""
    out = []
    for f in form_fields:
        values = [r.answers.get(str(f.id)) for r in rows]
        values = [v for v in values if v not in (None, "", [])]
        item: dict = {
            "fieldId": f.id,
            "label": f.label,
            "kind": f.kind,
            "answered": len(values),
        }
        if f.kind in CHOICES:
            counts: Counter = Counter()
            for v in values:
                for choice in v if isinstance(v, list) else [v]:
                    counts[choice] += 1
            item["counts"] = [
                {"option": o, "count": counts.get(o, 0)} for o in f.options or []
            ]
        elif f.kind == "yesno":
            item["counts"] = [
                {"option": "yes", "count": sum(1 for v in values if v is True)},
                {"option": "no", "count": sum(1 for v in values if v is False)},
            ]
        elif f.kind == "number":
            nums = [float(v) for v in values if isinstance(v, (int, float))]
            item["sum"] = round(sum(nums), 4) if nums else None
            item["average"] = round(sum(nums) / len(nums), 2) if nums else None
            item["min"] = min(nums) if nums else None
            item["max"] = max(nums) if nums else None
        else:
            item["values"] = [str(v) for v in values][-200:]
        out.append(item)
    return out


def text_of(f: FormsField, value, german: bool = True) -> str:
    """One answer as plain text (table and CSV)."""
    if value is None:
        return ""
    if f.kind == "yesno":
        return ("Ja" if german else "Yes") if value else ("Nein" if german else "No")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def delete_form(form: FormsForm) -> None:
    """The form with its fields and every answer.

    Club schemas are cloned without foreign keys, so ON DELETE CASCADE
    doesn't run there: the answers are deleted here.
    """
    db.session.execute(delete(FormsResponse).where(FormsResponse.form_id == form.id))
    db.session.execute(delete(FormsField).where(FormsField.form_id == form.id))
    db.session.delete(form)


def delete_answers_at(form: FormsForm) -> datetime | None:
    """When the form's answers are deleted: a year after it closed."""
    if form.status == "draft":
        return None
    closes = _aware(form.closes_at)
    if closes is None:
        if form.status != "closed":
            return None  # open with no end (made before ends were required)
        closes = _aware(form.opened_at or form.created_at)
    return closes + KEEP_ANSWERS


def purge_expired() -> int:
    """Deletes the answers of forms that closed more than a year ago; the
    form and its questions stay."""
    moment = now()
    expired = [
        form.id
        for form in db.session.scalars(
            select(FormsForm)
            .where(FormsForm.status != "draft")
            .where(FormsForm.id.in_(select(FormsResponse.form_id)))
        )
        if (at := delete_answers_at(form)) is not None and at <= moment
    ]
    if not expired:
        return 0
    return (
        db.session.execute(
            delete(FormsResponse).where(FormsResponse.form_id.in_(expired))
        ).rowcount
        or 0
    )


def purge_orphans() -> int:
    """Answers of members who are no longer in the club (deleted on request
    or after the retention time), and of forms that are gone. Club schemas
    have no foreign keys, so nothing else removes them."""
    gone = db.session.execute(
        delete(FormsResponse).where(
            FormsResponse.member_id.not_in(select(Member.id))
            | FormsResponse.form_id.not_in(select(FormsForm.id))
        )
    ).rowcount
    db.session.execute(
        delete(FormsField).where(FormsField.form_id.not_in(select(FormsForm.id)))
    )
    return gone or 0


def announce(form: FormsForm) -> int:
    """Tells the form's members it is open."""
    title = form.title[:200]
    return notify(
        audience(form),
        lambda de: ("Neues Formular" if de else "New form", title),
        f"/app/forms/{form.id}",
        topic="polls",
    )


def remind() -> int:
    """A day before an open form closes, those who haven't answered get a bell."""
    sent = 0
    moment = now()
    for form in db.session.scalars(
        select(FormsForm)
        .where(FormsForm.status == "open")
        .where(FormsForm.remind.is_(True))
        .where(FormsForm.reminded_at.is_(None))
        .where(FormsForm.closes_at.is_not(None))
    ):
        closes = _aware(form.closes_at)
        if not (moment < closes <= moment + REMIND_BEFORE):
            continue
        answered = set(
            db.session.scalars(
                select(FormsResponse.member_id).where(FormsResponse.form_id == form.id)
            )
        )
        missing = [m for m in audience(form) if m not in answered]
        title = form.title[:200]
        sent += notify(
            missing,
            lambda de, title=title: (
                ("Formular schliesst morgen", title)
                if de
                else ("Form closes tomorrow", title)
            ),
            f"/app/forms/{form.id}",
            topic="poll_reminders",
        )
        form.reminded_at = moment
    return sent

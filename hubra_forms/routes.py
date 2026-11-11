"""Forms API: /api/v1/app/forms.

GET    /options                     what the caller may do (and groups, for the board)
GET    /forms                       forms the caller can see, newest first
POST   /forms                       {title, description?, closesAt?, groupId?, anonymous?,
                                     resultsPublic?, remind?, fields: [...]}
GET    /forms/<id>                  with its fields and the caller's answer
PUT    /forms/<id>                  same body; fields with an id are kept, others added,
                                    missing ones removed
POST   /forms/<id>/status           {status: open|closed|draft, announce?}
POST   /forms/<id>/copy             a new draft with the same fields
DELETE /forms/<id>
PUT    /forms/<id>/response         {answers: {fieldId: value}}: the caller's answer
DELETE /forms/<id>/response         withdraw it while the form is open
GET    /forms/<id>/results          summary (and every answer for the board)
GET    /forms/<id>/results.csv      every answer (board)

A field: {id?, kind: text|textarea|number|date|choice|multi|yesno, label,
help?, required?, options?: [text]} (options for choice and multi).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy import func, select

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.group import Group
from hubra.core.permissions import permission_required, require_member
from hubra.core.utils import log_audit

from . import services
from .body import Invalid, _body, _bool, _can, _get, _int, _iso, _names, _text
from .models import FormsField, FormsForm, FormsResponse

forms_bp = Blueprint("forms_bp", __name__)

MANAGE = "forms.forms.update"
MAX_FIELDS = 60
MAX_OPTIONS = 50


@forms_bp.errorhandler(Invalid)
def _invalid(exc: Invalid):
    return api_error("VALIDATION_ERROR", exc.message, 400)


def _german(member) -> bool:
    return (getattr(member, "language", None) or "de").lower().startswith("de")


# ── Output ───────────────────────────────────────────────────────────────────


def _field(f: FormsField) -> dict:
    return {
        "id": f.id,
        "kind": f.kind,
        "label": f.label,
        "help": f.help,
        "required": f.required,
        "options": f.options or [],
    }


def _form(
    form: FormsForm, member, manage: bool, counts: dict, mine: set, groups: dict
) -> dict:
    out = {
        "id": form.id,
        "title": form.title,
        "description": form.description,
        "state": services.state(form),
        "closesAt": _iso(form.closes_at),
        "groupId": form.group_id,
        "groupName": groups.get(form.group_id) if form.group_id else None,
        "anonymous": form.anonymous,
        "resultsPublic": form.results_public,
        "remind": form.remind,
        "answered": form.id in mine,
        "openedAt": _iso(form.opened_at),
        "createdAt": _iso(form.created_at),
    }
    if manage:
        out["responses"] = counts.get(form.id, 0)
    return out


def _group_names(ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        g.id: g.name for g in db.session.scalars(select(Group).where(Group.id.in_(ids)))
    }


def _visible(form: FormsForm, member, manage: bool) -> bool:
    if manage:
        return True
    return form.status != "draft" and services.in_audience(member, form)


def _load(form_id: int):
    """The form, if the caller may see it (else 404, so drafts stay hidden)."""
    member = get_current_member()
    form = db.session.get(FormsForm, form_id)
    manage = _can(member, MANAGE)
    if form is None or not _visible(form, member, manage):
        return None, member, manage, api_error("NOT_FOUND", "not found", 404)
    return form, member, manage, None


def _detail(form: FormsForm, member, manage: bool) -> dict:
    mine = db.session.scalar(
        select(FormsResponse)
        .where(FormsResponse.form_id == form.id)
        .where(FormsResponse.member_id == member.id)
    )
    counts = {}
    if manage:
        counts[form.id] = db.session.scalar(
            select(func.count())
            .select_from(FormsResponse)
            .where(FormsResponse.form_id == form.id)
        )
    out = _form(
        form,
        member,
        manage,
        counts,
        {form.id} if mine else set(),
        _group_names([form.group_id]),
    )
    out["fields"] = [_field(f) for f in services.fields(form.id)]
    out["myAnswers"] = mine.answers if mine else None
    out["myAnsweredAt"] = _iso(mine.updated_at) if mine else None
    out["canAnswer"] = services.is_open(form) and services.in_audience(member, form)
    out["canSeeResults"] = manage or (form.results_public and mine is not None)
    out["manage"] = manage
    return out


# ── Options and list ─────────────────────────────────────────────────────────


@forms_bp.get("/options")
@require_member
def options():
    member = get_current_member()
    manage = _can(member, MANAGE)
    out = {"memberId": member.id, "can": {"manage": manage}}
    if manage:
        out["groups"] = [
            {"id": g.id, "name": g.name}
            for g in db.session.scalars(select(Group).order_by(func.lower(Group.name)))
        ]
    return jsonify(out)


@forms_bp.get("/forms")
@require_member
def list_forms():
    member = get_current_member()
    manage = _can(member, MANAGE)
    rows = list(
        db.session.scalars(
            select(FormsForm).order_by(FormsForm.created_at.desc(), FormsForm.id.desc())
        )
    )
    rows = [f for f in rows if _visible(f, member, manage)]
    ids = [f.id for f in rows] or [0]
    counts = dict(
        db.session.execute(
            select(FormsResponse.form_id, func.count())
            .where(FormsResponse.form_id.in_(ids))
            .group_by(FormsResponse.form_id)
        ).all()
    )
    mine = set(
        db.session.scalars(
            select(FormsResponse.form_id)
            .where(FormsResponse.form_id.in_(ids))
            .where(FormsResponse.member_id == member.id)
        )
    )
    groups = _group_names(f.group_id for f in rows)
    return jsonify([_form(f, member, manage, counts, mine, groups) for f in rows])


# ── Building ─────────────────────────────────────────────────────────────────


def _closes_at(data) -> datetime | None:
    value = data.get("closesAt")
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise Invalid("closesAt must be a time") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_zone())
    return moment.astimezone(timezone.utc)


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(current_app.config.get("MAIL_TIMEZONE") or "Europe/Zurich")
    except Exception:  # noqa: BLE001 - a bad setting falls back
        return ZoneInfo("Europe/Zurich")


def _has_answers(form: FormsForm) -> bool:
    return (
        bool(form.id)
        and db.session.scalar(
            select(FormsResponse.id).where(FormsResponse.form_id == form.id).limit(1)
        )
        is not None
    )


def _settings(form: FormsForm, data: dict) -> None:
    anonymous = _bool(data, "anonymous")
    if form.anonymous and not anonymous and _has_answers(form):
        # Members answered on the promise that nobody sees who said what.
        raise Invalid("an anonymous form with answers can't stop being anonymous")
    form.title = _text(data, "title", 200, required=True)
    form.description = _text(data, "description", 5000)
    form.closes_at = _closes_at(data)
    group_id = _int(data, "groupId", 1, 2**31 - 1)
    if group_id is not None and db.session.get(Group, group_id) is None:
        raise Invalid("groupId: no such group")
    form.group_id = group_id
    form.anonymous = anonymous
    form.results_public = _bool(data, "resultsPublic")
    form.remind = _bool(data, "remind")
    if form.remind and form.closes_at is None:
        raise Invalid("a reminder needs a closing time")


def _clean_field(raw) -> dict:
    if not isinstance(raw, dict):
        raise Invalid("each field must be an object")
    kind = raw.get("kind")
    if kind not in services.KINDS:
        raise Invalid("field kind must be one of " + ", ".join(services.KINDS))
    out = {
        "id": raw.get("id") if isinstance(raw.get("id"), int) else None,
        "kind": kind,
        "label": _text(raw, "label", 300, required=True),
        "help": _text(raw, "help", 500),
        "required": _bool(raw, "required"),
        "options": None,
    }
    if kind in services.CHOICES:
        opts = raw.get("options")
        if not isinstance(opts, list):
            raise Invalid(f"{out['label']}: choices are needed")
        seen: list[str] = []
        for o in opts:
            if not isinstance(o, str) or not o.strip():
                continue
            o = o.strip()[:200]
            if o not in seen:
                seen.append(o)
        if len(seen) < 2:
            raise Invalid(f"{out['label']}: at least two choices")
        if len(seen) > MAX_OPTIONS:
            raise Invalid(f"{out['label']}: at most {MAX_OPTIONS} choices")
        out["options"] = seen
    return out


def _save_fields(form: FormsForm, raw) -> None:
    if not isinstance(raw, list):
        raise Invalid("fields must be a list")
    if not raw:
        raise Invalid("a form needs at least one field")
    if len(raw) > MAX_FIELDS:
        raise Invalid(f"at most {MAX_FIELDS} fields")
    wanted = [_clean_field(r) for r in raw]
    existing = {f.id: f for f in services.fields(form.id)} if form.id else {}
    answered = _has_answers(form)
    keep = set()
    for pos, w in enumerate(wanted):
        f = existing.get(w["id"]) if w["id"] else None
        if f is None:
            f = FormsField(form_id=form.id)
            db.session.add(f)
        elif answered and f.kind != w["kind"]:
            raise Invalid(f"{f.label}: its kind can't change once there are answers")
        else:
            keep.add(f.id)
        f.position = pos
        f.kind = w["kind"]
        f.label = w["label"]
        f.help = w["help"]
        f.required = w["required"]
        f.options = w["options"]
    for fid, f in existing.items():
        if fid not in keep:
            db.session.delete(f)


@forms_bp.post("/forms")
@permission_required("forms", "update", "Build forms and see every answer")
def create_form():
    member = get_current_member()
    data = _body()
    form = FormsForm(created_by=member.id, status="draft")
    _settings(form, data)
    db.session.add(form)
    db.session.flush()
    _save_fields(form, data.get("fields"))
    log_audit(member.id, "forms.create", "FormsForm", form.id, form.title)
    db.session.commit()
    return jsonify(_detail(form, member, True)), 201


@forms_bp.put("/forms/<int:form_id>")
@permission_required("forms", "update", "Build forms and see every answer")
def update_form(form_id: int):
    member = get_current_member()
    form, err = _get(FormsForm, form_id)
    if err:
        return err
    data = _body()
    _settings(form, data)
    if form.reminded_at and form.closes_at and form.closes_at > services.now():
        form.reminded_at = None  # a new closing time gets its own reminder
    _save_fields(form, data.get("fields"))
    log_audit(member.id, "forms.update", "FormsForm", form.id, form.title)
    db.session.commit()
    return jsonify(_detail(form, member, True))


@forms_bp.post("/forms/<int:form_id>/status")
@permission_required("forms", "update", "Build forms and see every answer")
def set_status(form_id: int):
    member = get_current_member()
    form, err = _get(FormsForm, form_id)
    if err:
        return err
    data = _body()
    status = data.get("status")
    if status not in ("draft", "open", "closed"):
        raise Invalid("status must be draft, open or closed")
    if status == "draft" and db.session.scalar(
        select(FormsResponse.id).where(FormsResponse.form_id == form.id).limit(1)
    ):
        return api_error(
            "FORM_ANSWERED", "a form with answers can't go back to draft", 409
        )
    if (
        status == "open"
        and form.closes_at
        and services._aware(form.closes_at) <= services.now()
    ):
        raise Invalid("the closing time has passed; set a new one first")
    form.status = status
    sent = 0
    if status == "open":
        form.opened_at = form.opened_at or services.now()
        if _bool(data, "announce"):
            sent = services.announce(form)
    log_audit(member.id, f"forms.{status}", "FormsForm", form.id, form.title)
    db.session.commit()
    out = _detail(form, member, True)
    out["announced"] = sent
    return jsonify(out)


@forms_bp.post("/forms/<int:form_id>/copy")
@permission_required("forms", "update", "Build forms and see every answer")
def copy_form(form_id: int):
    member = get_current_member()
    src, err = _get(FormsForm, form_id)
    if err:
        return err
    form = FormsForm(
        title=(src.title + " (Kopie)" if _german(member) else src.title + " (copy)")[
            :200
        ],
        description=src.description,
        status="draft",
        group_id=src.group_id,
        anonymous=src.anonymous,
        results_public=src.results_public,
        remind=False,
        created_by=member.id,
    )
    db.session.add(form)
    db.session.flush()
    for f in services.fields(src.id):
        db.session.add(
            FormsField(
                form_id=form.id,
                position=f.position,
                kind=f.kind,
                label=f.label,
                help=f.help,
                required=f.required,
                options=list(f.options) if f.options else None,
            )
        )
    log_audit(member.id, "forms.copy", "FormsForm", form.id, form.title)
    db.session.commit()
    return jsonify(_detail(form, member, True)), 201


@forms_bp.delete("/forms/<int:form_id>")
@permission_required("forms", "update", "Build forms and see every answer")
def delete_form(form_id: int):
    member = get_current_member()
    form, err = _get(FormsForm, form_id)
    if err:
        return err
    log_audit(member.id, "forms.delete", "FormsForm", form.id, form.title)
    services.delete_form(form)
    db.session.commit()
    return "", 204


# ── Answering ────────────────────────────────────────────────────────────────


@forms_bp.get("/forms/<int:form_id>")
@require_member
def get_form(form_id: int):
    form, member, manage, err = _load(form_id)
    if err:
        return err
    return jsonify(_detail(form, member, manage))


@forms_bp.put("/forms/<int:form_id>/response")
@require_member
def answer(form_id: int):
    form, member, manage, err = _load(form_id)
    if err:
        return err
    if not services.in_audience(member, form):
        return api_error("FORBIDDEN", "this form is for another group", 403)
    if not services.is_open(form):
        return api_error("FORM_CLOSED", "this form is closed", 409)
    try:
        answers = services.clean(services.fields(form.id), _body().get("answers"))
    except services.BadAnswer as exc:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": exc.message,
                "fieldId": exc.field_id,
            }
        ), 400
    row = db.session.scalar(
        select(FormsResponse)
        .where(FormsResponse.form_id == form.id)
        .where(FormsResponse.member_id == member.id)
        .with_for_update()
    )
    if row is None:
        row = FormsResponse(form_id=form.id, member_id=member.id, answers=answers)
        db.session.add(row)
    else:
        row.answers = answers
        row.updated_at = services.now()
    db.session.commit()
    return jsonify(_detail(form, member, manage))


@forms_bp.delete("/forms/<int:form_id>/response")
@require_member
def withdraw(form_id: int):
    form, member, manage, err = _load(form_id)
    if err:
        return err
    if not services.is_open(form):
        return api_error("FORM_CLOSED", "this form is closed", 409)
    row = db.session.scalar(
        select(FormsResponse)
        .where(FormsResponse.form_id == form.id)
        .where(FormsResponse.member_id == member.id)
    )
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    return jsonify(_detail(form, member, manage))


# ── Results ──────────────────────────────────────────────────────────────────


def _rows(
    form: FormsForm,
    form_fields: list[FormsField],
    rows: list[FormsResponse],
    german: bool,
):
    names = {} if form.anonymous else _names(r.member_id for r in rows)
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "name": None if form.anonymous else names.get(r.member_id, "?"),
                "memberId": None if form.anonymous else r.member_id,
                "at": None if form.anonymous else _iso(r.updated_at),
                "answers": {
                    str(f.id): services.text_of(f, r.answers.get(str(f.id)), german)
                    for f in form_fields
                },
            }
        )
    if form.anonymous:
        # The time and order of an answer can tell who gave it (the board
        # knows who was told first); sort by the answers and number the rows.
        out.sort(key=lambda row: [row["answers"][str(f.id)] for f in form_fields])
        for pos, row in enumerate(out, 1):
            row["id"] = pos
    return out


@forms_bp.get("/forms/<int:form_id>/results")
@require_member
def results(form_id: int):
    form, member, manage, err = _load(form_id)
    if err:
        return err
    form_fields = services.fields(form.id)
    rows = services.responses(form.id)
    if not manage:
        answered = any(r.member_id == member.id for r in rows)
        if not (form.results_public and answered):
            return api_error("FORBIDDEN", "the results are for the board", 403)
    out = {
        "responses": len(rows),
        "fields": [_field(f) for f in form_fields],
        "summary": services.summary(form_fields, rows),
    }
    if manage:
        out["rows"] = _rows(form, form_fields, rows, _german(member))
        if not form.anonymous:
            answered_ids = {r.member_id for r in rows}
            out["missing"] = sorted(
                _names(
                    m for m in services.audience(form) if m not in answered_ids
                ).values(),
                key=str.lower,
            )
    else:
        # Free text could name people; members see counts and figures only.
        for item in out["summary"]:
            item.pop("values", None)
    return jsonify(out)


def _safe(cell: str) -> str:
    # A cell starting like a formula would run in a spreadsheet.
    return "'" + cell if cell[:1] in ("=", "+", "-", "@", "\t", "\r") else cell


@forms_bp.get("/forms/<int:form_id>/results.csv")
@permission_required("forms", "update", "Build forms and see every answer")
def results_csv(form_id: int):
    member = get_current_member()
    form, err = _get(FormsForm, form_id)
    if err:
        return err
    german = _german(member)
    form_fields = services.fields(form.id)
    rows = _rows(form, form_fields, services.responses(form.id), german)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    # Anonymous forms leave out who answered and when.
    head = [] if form.anonymous else ["Name", "Beantwortet" if german else "Answered"]
    writer.writerow([_safe(h) for h in head + [f.label for f in form_fields]])
    for r in rows:
        line = (
            []
            if form.anonymous
            else [r["name"], (r["at"] or "")[:16].replace("T", " ")]
        )
        line += [r["answers"][str(f.id)] for f in form_fields]
        writer.writerow([_safe(str(c)) for c in line])
    log_audit(member.id, "forms.export", "FormsForm", form.id, form.title)
    db.session.commit()
    # ASCII only: a header can't carry other characters.
    name = (
        "".join(c if c.isascii() and c.isalnum() else "-" for c in form.title).strip(
            "-"
        )[:60]
        or "form"
    )
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )

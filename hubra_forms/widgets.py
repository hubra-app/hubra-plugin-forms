"""Dashboard widgets of Forms (docs/dashboards.md in hubra-app/hubra).

forms.todo  list  open forms the viewer may fill in and hasn't yet, the ones
                  closing first on top

It reads as the viewing member; every member with Forms sees it.
"""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.extensions import db

from . import services
from .models import FormsForm, FormsResponse


def _german(member) -> bool:
    return (getattr(member, "language", None) or "de").lower().startswith("de")


def _count(config: dict) -> int:
    try:
        return max(1, min(int(config.get("count") or 5), 20))
    except (TypeError, ValueError):
        return 5


def todo(ctx, config: dict) -> dict:
    me = ctx.actor
    if me is None:
        return {"items": [], "total": 0}
    answered = select(FormsResponse.form_id).where(FormsResponse.member_id == me.id)
    forms = [
        f
        for f in db.session.scalars(
            select(FormsForm)
            .where(FormsForm.status == "open")
            .where(FormsForm.id.not_in(answered))
            .order_by(FormsForm.closes_at.is_(None), FormsForm.closes_at, FormsForm.id)
        )
        if services.is_open(f) and services.in_audience(me, f)
    ]
    until = "bis" if _german(me) else "until"
    items = [
        {
            "label": f.title,
            "sub": f"{until} {services._aware(f.closes_at):%d.%m.%Y}" if f.closes_at else None,
            "path": f"/app/forms/{f.id}",
        }
        for f in forms[: _count(config)]
    ]
    return {"items": items, "total": len(forms)}

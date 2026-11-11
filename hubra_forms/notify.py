"""Bell notifications in each member's language."""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.notifications.services import notify_member


def _german(member: Member) -> bool:
    return (getattr(member, "language", None) or "de").lower().startswith("de")


def notify(member_ids, texts, link: str, topic: str) -> int:
    """*texts* is a function of ``german: bool`` returning ``(title, message)``.

    *topic* is one of Hubra's notification topics, so a member who turned it
    off doesn't get the bell: forms go with the polls (``polls`` for a new
    one, ``poll_reminders`` for the reminder). Returns how many active
    members it was for."""
    ids = sorted({m for m in member_ids if m})
    if not ids:
        return 0
    sent = 0
    for member in db.session.scalars(
        select(Member)
        .where(Member.id.in_(ids))
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
    ):
        title, msg = texts(_german(member))
        notify_member(member.id, "info", title, msg, link=link, topic=topic)
        sent += 1
    return sent

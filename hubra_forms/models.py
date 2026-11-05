"""The Forms tables (one copy per club schema)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FormsForm(db.Model):
    __tablename__ = "forms_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # draft (only the board sees it), open, closed
    status: Mapped[str] = mapped_column(String(10), default="draft", nullable=False)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Only this group's members see and answer it; None: every member.
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL")
    )
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Members see the summary of all answers once they answered.
    results_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # A bell one day before closing to those who haven't answered.
    remind: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FormsField(db.Model):
    __tablename__ = "forms_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(
        ForeignKey("forms_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # text, textarea, number, date, choice, multi, yesno
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    help: Mapped[str | None] = mapped_column(String(500))
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON)


class FormsResponse(db.Model):
    __tablename__ = "forms_responses"
    __table_args__ = (
        UniqueConstraint("form_id", "member_id", name="uq_forms_response"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(
        ForeignKey("forms_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kept on anonymous forms too, so each member answers once; never shown there.
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    # {field id (as text): value}
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

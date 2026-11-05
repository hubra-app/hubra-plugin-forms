"""forms: forms, fields and responses

Runs in public and in every club's schema, tracked in its own version table
(alembic_version_forms). has_table() keeps it safe to run twice.

Revision ID: 4c7e1a9b3f20
Revises:
Create Date: 2026-11-05 17:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "4c7e1a9b3f20"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade():
    if not has_table("forms_forms"):
        op.create_table(
            "forms_forms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(10), nullable=False),
            _ts("closes_at"),
            sa.Column("group_id", sa.Integer(), nullable=True),
            sa.Column("anonymous", sa.Boolean(), nullable=False),
            sa.Column("results_public", sa.Boolean(), nullable=False),
            sa.Column("remind", sa.Boolean(), nullable=False),
            _ts("reminded_at"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            _ts("created_at", nullable=False),
            _ts("opened_at"),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["created_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not has_table("forms_fields"):
        op.create_table(
            "forms_fields",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("form_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("label", sa.String(300), nullable=False),
            sa.Column("help", sa.String(500), nullable=True),
            sa.Column("required", sa.Boolean(), nullable=False),
            sa.Column("options", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["form_id"], ["forms_forms.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_forms_fields_form_id", "forms_fields", ["form_id"])
    if not has_table("forms_responses"):
        op.create_table(
            "forms_responses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("form_id", sa.Integer(), nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=False),
            sa.Column("answers", sa.JSON(), nullable=False),
            _ts("created_at", nullable=False),
            _ts("updated_at", nullable=False),
            sa.ForeignKeyConstraint(
                ["form_id"], ["forms_forms.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("form_id", "member_id", name="uq_forms_response"),
        )
        op.create_index("ix_forms_responses_form_id", "forms_responses", ["form_id"])


def downgrade():
    for table in ("forms_responses", "forms_fields", "forms_forms"):
        if has_table(table):
            op.drop_table(table)

"""AI sources (control tower) and crisis events (storm mode)

- ai_sources: every AI system that proposes suggestions; external ones use an API key.
- suggestions.source / latency_ms: which system produced a suggestion, how fast.
- crisis_events + emails.event_id: e-mails that belong to a declared climate event.

Existing suggestions are attributed to the internal pipeline ("interne").

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_sources",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("api_key_hash", name="uq_ai_sources_api_key_hash"),
    )
    op.create_table(
        "crisis_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("suggestions") as batch:
        batch.add_column(
            sa.Column("source", sa.String(length=40), nullable=False, server_default="interne")
        )
        batch.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        batch.create_index("ix_suggestions_source", ["source"])
    with op.batch_alter_table("emails") as batch:
        batch.add_column(sa.Column("event_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_emails_event_id", "crisis_events", ["event_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_emails_event_id", ["event_id"])


def downgrade() -> None:
    with op.batch_alter_table("emails") as batch:
        batch.drop_index("ix_emails_event_id")
        batch.drop_constraint("fk_emails_event_id", type_="foreignkey")
        batch.drop_column("event_id")
    with op.batch_alter_table("suggestions") as batch:
        batch.drop_index("ix_suggestions_source")
        batch.drop_column("latency_ms")
        batch.drop_column("source")
    op.drop_table("crisis_events")
    op.drop_table("ai_sources")

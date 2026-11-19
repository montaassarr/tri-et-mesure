"""casework, async analysis, runtime config

Adds the case lifecycle (queue time, closing time, handler lease), the asynchronous
analysis state, the runtime AI configuration table, one-decision-per-case uniqueness
and the indexes used by the queue, the worker and the budget check.

Existing rows are backfilled: analysed e-mails become "done", closed cases get their
closing time from their review.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    with op.batch_alter_table("emails") as batch:
        batch.add_column(
            sa.Column(
                "queued_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("assigned_to", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "analysis_status", sa.String(length=10), nullable=False, server_default="done"
            )
        )
        batch.add_column(
            sa.Column("analysis_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("analysis_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("analysis_error", sa.String(length=300), nullable=True))
        batch.create_index("ix_emails_analysis_status", ["analysis_status"])
        batch.create_index("ix_emails_status", ["status"])

    # Backfill: e-mails without a suggestion still need an analysis.
    op.execute(
        "UPDATE emails SET analysis_status = 'pending' "
        "WHERE id NOT IN (SELECT email_id FROM suggestions)"
    )

    with op.batch_alter_table("reviews") as batch:
        batch.add_column(
            sa.Column(
                "reviewer_role",
                sa.String(length=20),
                nullable=False,
                server_default="gestionnaire",
            )
        )
        batch.create_unique_constraint("uq_reviews_email_id", ["email_id"])

    op.execute(
        "UPDATE emails SET closed_at = (SELECT MIN(r.created_at) FROM reviews r "
        "WHERE r.email_id = emails.id) WHERE status <> 'nouveau'"
    )

    op.create_index("ix_audit_events_email_id", "audit_events", ["email_id"])
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_audit_events_email_id", table_name="audit_events")
    with op.batch_alter_table("reviews") as batch:
        batch.drop_constraint("uq_reviews_email_id", type_="unique")
        batch.drop_column("reviewer_role")
    with op.batch_alter_table("emails") as batch:
        batch.drop_index("ix_emails_status")
        batch.drop_index("ix_emails_analysis_status")
        for column in (
            "analysis_error",
            "analysis_started_at",
            "analysis_attempts",
            "analysis_status",
            "assigned_at",
            "assigned_to",
            "closed_at",
            "queued_at",
        ):
            batch.drop_column(column)
    op.drop_table("app_config")

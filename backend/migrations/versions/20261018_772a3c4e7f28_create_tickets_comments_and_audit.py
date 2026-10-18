"""create tickets, comments and audit entries

Revision ID: 772a3c4e7f28
Revises:
Create Date: 2026-10-18 10:54:02.419097+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "772a3c4e7f28"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint(
            "requester_id", "idempotency_key", name="uq_tickets_requester_id_idempotency_key"
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="ck_tickets_priority"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting_on_customer', 'resolved', 'closed')",
            name="ck_tickets_status",
        ),
        sa.CheckConstraint(
            "status NOT IN ('in_progress', 'waiting_on_customer') OR assignee_id IS NOT NULL",
            name="ck_tickets_worked_ticket_has_assignee",
        ),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_comments_ticket_id_tickets"
        ),
        sa.CheckConstraint("visibility IN ('public', 'internal')", name="ck_comments_visibility"),
    )
    op.create_index("ix_comments_ticket_id_created_at", "comments", ["ticket_id", "created_at"])

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_entries"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name="fk_audit_entries_ticket_id_tickets"
        ),
    )
    op.create_index(
        "ix_audit_entries_ticket_id_occurred_at", "audit_entries", ["ticket_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
    op.drop_table("comments")
    op.drop_table("tickets")

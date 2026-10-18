"""flag first-response breaches and let the system act on tickets

Revision ID: d81a6f3e0b54
Revises: b3f0c95a1d27
Create Date: 2026-10-18 13:40:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d81a6f3e0b54"
down_revision: str | None = "b3f0c95a1d27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AWAITING_FIRST_RESPONSE = (
    "first_responded_at IS NULL AND sla_breached_at IS NULL"
    " AND status IN ('open', 'in_progress', 'waiting_on_customer')"
)


def upgrade() -> None:
    op.add_column(
        "tickets", sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_tickets_awaiting_first_response",
        "tickets",
        ["created_at"],
        postgresql_where=sa.text(_AWAITING_FIRST_RESPONSE),
    )
    op.create_index(
        "ix_tickets_resolved_at",
        "tickets",
        ["resolved_at"],
        postgresql_where=sa.text("status = 'resolved'"),
    )
    op.alter_column("audit_entries", "actor_id", nullable=True)


def downgrade() -> None:
    # Entries the system wrote have no actor and can't satisfy NOT NULL again. Deleting audit
    # history to make a downgrade pass is worse than stopping, so stop and say why.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM audit_entries WHERE actor_id IS NULL) THEN
                RAISE EXCEPTION 'audit_entries has rows written by the system (actor_id IS NULL);'
                    ' archive or remove them deliberately before downgrading';
            END IF;
        END $$
        """
    )
    op.alter_column("audit_entries", "actor_id", nullable=False)
    op.drop_index("ix_tickets_resolved_at", table_name="tickets")
    op.drop_index("ix_tickets_awaiting_first_response", table_name="tickets")
    op.drop_column("tickets", "sla_breached_at")

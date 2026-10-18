"""index the ticket list views

Revision ID: 9e41b7d2c6a0
Revises: 5c8266742115
Create Date: 2026-10-18 13:05:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9e41b7d2c6a0"
down_revision: str | None = "5c8266742115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = {
    "ix_tickets_created_at_id": ["created_at", "id"],
    "ix_tickets_updated_at_id": ["updated_at", "id"],
    "ix_tickets_requester_id_created_at_id": ["requester_id", "created_at", "id"],
    "ix_tickets_status_created_at_id": ["status", "created_at", "id"],
    "ix_tickets_assignee_id_updated_at_id": ["assignee_id", "updated_at", "id"],
}


def upgrade() -> None:
    for name, columns in _INDEXES.items():
        op.create_index(name, "tickets", columns)


def downgrade() -> None:
    for name in _INDEXES:
        op.drop_index(name, table_name="tickets")

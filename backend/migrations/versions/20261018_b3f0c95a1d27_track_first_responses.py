"""track when staff first responded to a ticket

Revision ID: b3f0c95a1d27
Revises: 9e41b7d2c6a0
Create Date: 2026-10-18 13:20:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f0c95a1d27"
down_revision: str | None = "9e41b7d2c6a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets", sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Tickets that already have a public staff reply would otherwise look unanswered.
    op.execute(
        """
        UPDATE tickets
        SET first_responded_at = first_reply.created_at
        FROM (
            SELECT comments.ticket_id, min(comments.created_at) AS created_at
            FROM comments
            JOIN users ON users.id = comments.author_id
            WHERE comments.visibility = 'public' AND users.role IN ('agent', 'admin')
            GROUP BY comments.ticket_id
        ) AS first_reply
        WHERE tickets.id = first_reply.ticket_id
        """
    )


def downgrade() -> None:
    op.drop_column("tickets", "first_responded_at")

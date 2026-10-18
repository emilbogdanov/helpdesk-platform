"""add users and link them to tickets, comments and audit entries

Revision ID: 5c8266742115
Revises: 772a3c4e7f28
Create Date: 2026-10-18 11:08:46.200586+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c8266742115"
down_revision: str | None = "772a3c4e7f28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('customer', 'agent', 'admin')", name="ck_users_role"),
    )
    # Tickets, comments and audit entries existed before users did; from here on every
    # person they mention must be a real account.
    for table, column in _USER_REFERENCES:
        op.create_foreign_key(f"fk_{table}_{column}_users", table, "users", [column], ["id"])


def downgrade() -> None:
    for table, column in reversed(_USER_REFERENCES):
        op.drop_constraint(f"fk_{table}_{column}_users", table, type_="foreignkey")
    op.drop_table("users")


_USER_REFERENCES = [
    ("tickets", "requester_id"),
    ("tickets", "assignee_id"),
    ("comments", "author_id"),
    ("audit_entries", "actor_id"),
]

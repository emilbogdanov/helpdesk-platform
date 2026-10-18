"""index people by name for the admin account list

Revision ID: e5a7c1d3f092
Revises: d81a6f3e0b54
Create Date: 2026-10-18 19:20:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5a7c1d3f092"
down_revision: str | None = "d81a6f3e0b54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_users_display_name_id", "users", ["display_name", "id"])


def downgrade() -> None:
    op.drop_index("ix_users_display_name_id", table_name="users")

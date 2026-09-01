"""drop stats_unlocked from user_settings

Revision ID: e43ce4ff123a
Revises: 3f9a1c2b7d84
Create Date: 2026-05-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e43ce4ff123a"
down_revision: str | None = "3f9a1c2b7d84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("user_settings", "stats_unlocked")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_settings",
        sa.Column(
            "stats_unlocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

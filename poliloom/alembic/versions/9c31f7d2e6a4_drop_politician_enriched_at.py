"""drop politician enriched_at

Revision ID: 9c31f7d2e6a4
Revises: 8f39c2a17b4d
Create Date: 2026-07-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9c31f7d2e6a4"
down_revision: Union[str, None] = "8f39c2a17b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("politicians", "enriched_at")


def downgrade() -> None:
    op.add_column(
        "politicians",
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
    )

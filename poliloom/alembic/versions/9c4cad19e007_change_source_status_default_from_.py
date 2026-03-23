"""change source status default from pending to processing

Revision ID: 9c4cad19e007
Revises: 6a5056f454b3
Create Date: 2026-03-23 15:52:27.270714

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9c4cad19e007"
down_revision: Union[str, None] = "6a5056f454b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "sources",
        "status",
        server_default="PROCESSING",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "sources",
        "status",
        server_default="PENDING",
    )

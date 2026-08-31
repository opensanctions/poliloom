"""add embedding column to country model

Revision ID: ca1f55abed5b
Revises: e7369f077a07
Create Date: 2025-09-25 12:39:59.628768

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "ca1f55abed5b"
down_revision: Union[str, None] = "e7369f077a07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

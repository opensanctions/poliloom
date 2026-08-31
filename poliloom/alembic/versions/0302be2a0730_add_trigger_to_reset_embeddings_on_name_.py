"""add trigger to reset embeddings on name change

Revision ID: 0302be2a0730
Revises: 146440e7d68e
Create Date: 2025-09-10 21:17:57.683955

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0302be2a0730"
down_revision: Union[str, None] = "146440e7d68e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

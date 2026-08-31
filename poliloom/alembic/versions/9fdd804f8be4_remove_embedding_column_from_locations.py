"""remove embedding column from locations

Revision ID: 9fdd804f8be4
Revises: cfdbf2ed21ed
Create Date: 2025-10-09 10:31:45.606653

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "9fdd804f8be4"
down_revision: Union[str, None] = "cfdbf2ed21ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

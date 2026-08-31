"""remove embedding column from locations

Revision ID: 9fdd804f8be4
Revises: cfdbf2ed21ed
Create Date: 2025-10-09 10:31:45.606653

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9fdd804f8be4"
down_revision: str | None = "cfdbf2ed21ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

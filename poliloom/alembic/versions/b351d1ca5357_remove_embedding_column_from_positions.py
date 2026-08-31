"""remove embedding column from positions

Revision ID: b351d1ca5357
Revises: d6772e534c56
Create Date: 2025-12-14 15:30:55.249491

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b351d1ca5357"
down_revision: str | None = "d6772e534c56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

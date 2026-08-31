"""update_embedding_reset_trigger_positions_only

Revision ID: 3111e43b8ec0
Revises: d76707579b83
Create Date: 2025-10-09 11:38:04.827354

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "3111e43b8ec0"
down_revision: str | None = "d76707579b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

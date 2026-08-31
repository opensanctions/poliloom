"""reset_embeddings_for_new_model

Revision ID: e5b6261690bf
Revises: ce8ea667765a
Create Date: 2025-09-25 23:14:55.713610

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e5b6261690bf"
down_revision: str | None = "ce8ea667765a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

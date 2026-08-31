"""drop vector extension

Revision ID: 3f9a1c2b7d84
Revises: bce118d9a29f

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f9a1c2b7d84"
down_revision: str | None = "bce118d9a29f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: the vector extension cannot be restored without the pgvector binary.

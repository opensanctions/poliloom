"""remove embedding column from countries

Revision ID: d76707579b83
Revises: 8a5582ba44f4
Create Date: 2025-10-09 10:55:39.507017

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d76707579b83"
down_revision: str | None = "8a5582ba44f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # No-op: embeddings removed from migration history.


def downgrade() -> None:
    """Downgrade schema."""
    # No-op: embeddings removed from migration history.

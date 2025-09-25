"""reset_embeddings_for_new_model

Revision ID: e5b6261690bf
Revises: ce8ea667765a
Create Date: 2025-09-25 23:14:55.713610

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5b6261690bf"
down_revision: Union[str, None] = "ce8ea667765a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reset all embedding columns to NULL for new embedding model."""
    # Update countries table
    op.execute("UPDATE countries SET embedding = NULL")

    # Update positions table
    op.execute("UPDATE positions SET embedding = NULL")

    # Update locations table
    op.execute("UPDATE locations SET embedding = NULL")


def downgrade() -> None:
    """No downgrade available - embeddings cannot be restored."""
    pass

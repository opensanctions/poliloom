"""remove_countries_without_iso_code

Revision ID: c39f3d863772
Revises: 172f4b4de36f
Create Date: 2025-09-19 16:02:18.827576

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c39f3d863772"
down_revision: Union[str, None] = "172f4b4de36f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Delete all countries that don't have ISO codes.
    This will cascade delete related has_citizenship records.
    """
    op.execute(
        """
        TRUNCATE countries CASCADE
    """
    )


def downgrade() -> None:
    """
    This migration is not reversible as it deletes data.
    The data can only be restored by re-importing from Wikidata dump.
    """
    raise NotImplementedError(
        "This migration cannot be reversed. Data must be restored from Wikidata dump."
    )

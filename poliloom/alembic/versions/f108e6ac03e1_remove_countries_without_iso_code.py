"""remove_countries_without_iso_code

Revision ID: f108e6ac03e1
Revises: 97de81eb2339
Create Date: 2025-01-19 16:20:31.507685

This migration removes all countries that don't have an ISO code,
as we've changed our import strategy to only include proper countries with ISO codes.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f108e6ac03e1"
down_revision: Union[str, None] = "97de81eb2339"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Delete all countries that don't have ISO codes.
    This will cascade delete related has_citizenship records.
    """

    # Delete countries without ISO codes
    op.execute("""
        DELETE FROM countries
        WHERE iso_code IS NULL
    """)


def downgrade() -> None:
    """
    This migration is not reversible as it deletes data.
    The data can only be restored by re-importing from Wikidata dump.
    """
    raise NotImplementedError(
        "This migration cannot be reversed. Data must be restored from Wikidata dump."
    )

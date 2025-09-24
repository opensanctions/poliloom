"""store raw wikidata time strings in properties

Revision ID: 705dddab0368
Revises: 9f7413ea7cc1
Create Date: 2025-09-24 17:30:51.300774

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "705dddab0368"
down_revision: Union[str, None] = "9f7413ea7cc1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove all Properties to prepare for new Wikidata time string format.

    This migration prepares for switching to raw Wikidata time strings by:
    1. Truncating all Properties (they will be re-imported with new format)
    """
    # Truncate all properties - they will be re-imported with the new time string format
    op.execute("TRUNCATE TABLE properties CASCADE")


def downgrade() -> None:
    """
    Downgrade schema.

    Note: This downgrade cannot restore the deleted Properties or cleared values.
    You will need to restore from backup or re-run imports.
    """
    # Cannot restore deleted Properties or cleared values
    pass

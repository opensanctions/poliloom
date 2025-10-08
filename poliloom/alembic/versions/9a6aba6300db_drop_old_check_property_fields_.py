"""drop_old_check_property_fields_constraint

Revision ID: 9a6aba6300db
Revises: cbbf26f62a09
Create Date: 2025-10-08 17:22:38.737411

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9a6aba6300db"
down_revision: Union[str, None] = "cbbf26f62a09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("check_property_fields", "properties", type_="check")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the old constraint without value_precision check
    op.execute(
        """
        ALTER TABLE properties ADD CONSTRAINT check_property_fields
        CHECK (
            (type IN ('BIRTH_DATE', 'DEATH_DATE') AND value IS NOT NULL AND entity_id IS NULL)
            OR
            (type IN ('BIRTHPLACE', 'POSITION', 'CITIZENSHIP') AND entity_id IS NOT NULL AND value IS NULL)
        );
        """
    )

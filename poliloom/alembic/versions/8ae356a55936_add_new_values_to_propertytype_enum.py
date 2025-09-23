"""Add new values to PropertyType enum

Revision ID: 8ae356a55936
Revises: 4b2fb2f20669
Create Date: 2025-09-23 21:39:18.178231

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8ae356a55936"
down_revision: Union[str, None] = "4b2fb2f20669"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new values to the PropertyType enum (using uppercase to match existing pattern)
    # Check if values already exist to avoid errors
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'propertytype' AND e.enumlabel = 'BIRTHPLACE') THEN
                ALTER TYPE propertytype ADD VALUE 'BIRTHPLACE';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'propertytype' AND e.enumlabel = 'POSITION') THEN
                ALTER TYPE propertytype ADD VALUE 'POSITION';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'propertytype' AND e.enumlabel = 'CITIZENSHIP') THEN
                ALTER TYPE propertytype ADD VALUE 'CITIZENSHIP';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL does not support removing enum values
    # This would require recreating the enum type and updating all references
    # For simplicity, we'll leave this as a no-op since enum values can't be easily removed
    pass

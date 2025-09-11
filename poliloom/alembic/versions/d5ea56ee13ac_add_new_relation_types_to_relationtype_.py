"""add new relation types to relationtype enum

Revision ID: d5ea56ee13ac
Revises: dd9ba46e21cd
Create Date: 2025-09-10 14:01:03.404584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5ea56ee13ac'
down_revision: Union[str, None] = 'dd9ba46e21cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum values to relationtype enum
    op.execute("ALTER TYPE relationtype ADD VALUE 'INSTANCE_OF'")  # P31
    op.execute("ALTER TYPE relationtype ADD VALUE 'PART_OF'")  # P361
    op.execute("ALTER TYPE relationtype ADD VALUE 'LOCATED_IN'")  # P131
    op.execute("ALTER TYPE relationtype ADD VALUE 'COUNTRY'")  # P17
    op.execute("ALTER TYPE relationtype ADD VALUE 'APPLIES_TO_JURISDICTION'")  # P1001


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type and updating all references
    # For this migration, we'll leave the enum values in place on downgrade
    pass

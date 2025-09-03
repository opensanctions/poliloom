"""convert property type to enum

Revision ID: 4797852d86b9
Revises: aa07180f92ea
Create Date: 2025-09-03 22:47:36.056245

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from poliloom.models import PropertyType


# revision identifiers, used by Alembic.
revision: str = "4797852d86b9"
down_revision: Union[str, None] = "aa07180f92ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type using the imported PropertyType
    propertytype_enum = sa.Enum(PropertyType, name="propertytype")
    propertytype_enum.create(op.get_bind())

    # Then alter the column to use the enum
    op.alter_column(
        "properties",
        "type",
        existing_type=sa.VARCHAR(),
        type_=propertytype_enum,
        postgresql_using="type::propertytype",
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # First alter the column back to VARCHAR
    op.alter_column(
        "properties",
        "type",
        existing_type=sa.Enum(PropertyType, name="propertytype"),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    # Then drop the enum type
    propertytype_enum = sa.Enum(PropertyType, name="propertytype")
    propertytype_enum.drop(op.get_bind())

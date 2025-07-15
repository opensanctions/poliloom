"""Add unique constraints for UPSERT operations

Revision ID: add_unique_constraints
Revises: add_precision_columns
Create Date: 2025-07-15 21:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_unique_constraints"
down_revision: Union[str, None] = "add_precision_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraints needed for UPSERT operations.

    This adds unique constraints to support ON CONFLICT DO UPDATE
    operations for efficient re-import handling.
    """
    # Add unique constraint on (politician_id, type) for properties
    # This ensures each politician can only have one property of each type
    op.create_unique_constraint(
        "uq_properties_politician_type", "properties", ["politician_id", "type"]
    )


def downgrade() -> None:
    """Remove unique constraints."""
    # Remove unique constraint from properties table
    op.drop_constraint("uq_properties_politician_type", "properties", type_="unique")

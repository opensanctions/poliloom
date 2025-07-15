"""Add precision columns to HoldsPosition and Property models

Revision ID: add_precision_columns
Revises: 47390e7bb18e
Create Date: 2025-07-15 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_precision_columns"
down_revision: Union[str, None] = "47390e7bb18e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add precision columns to store Wikidata date precision integers.

    This enables more accurate date comparisons and conflict resolution
    by storing the original precision from Wikidata (9=year, 10=month, 11=day).
    """
    # Add precision columns to HoldsPosition table
    op.add_column(
        "holds_position", sa.Column("start_date_precision", sa.Integer(), nullable=True)
    )
    op.add_column(
        "holds_position", sa.Column("end_date_precision", sa.Integer(), nullable=True)
    )

    # Add precision column to Property table for date properties
    op.add_column(
        "properties", sa.Column("value_precision", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    """Remove precision columns from HoldsPosition and Property models."""
    # Remove precision columns from HoldsPosition table
    op.drop_column("holds_position", "end_date_precision")
    op.drop_column("holds_position", "start_date_precision")

    # Remove precision column from Property table
    op.drop_column("properties", "value_precision")

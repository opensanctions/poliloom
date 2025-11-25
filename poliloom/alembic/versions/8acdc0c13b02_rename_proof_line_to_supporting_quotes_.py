"""rename proof_line to supporting_quotes array

Revision ID: 8acdc0c13b02
Revises: cba9fff2bbbe
Create Date: 2025-11-25 11:54:40.856918

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8acdc0c13b02"
down_revision: Union[str, None] = "cba9fff2bbbe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: convert proof_line (String) to supporting_quotes (ARRAY(String)).

    Migrates existing single proof_line values into single-element arrays.
    """
    # Add new supporting_quotes column as ARRAY(String)
    op.add_column(
        "properties",
        sa.Column("supporting_quotes", postgresql.ARRAY(sa.String()), nullable=True),
    )

    # Migrate existing data: convert single proof_line to single-element array
    op.execute(
        """
        UPDATE properties
        SET supporting_quotes = ARRAY[proof_line]
        WHERE proof_line IS NOT NULL
        """
    )

    # Drop the old proof_line column
    op.drop_column("properties", "proof_line")


def downgrade() -> None:
    """Downgrade schema: convert supporting_quotes back to proof_line.

    Takes the first quote from the array (if any) as the proof_line value.
    """
    # Add back the proof_line column
    op.add_column(
        "properties",
        sa.Column("proof_line", sa.String(), nullable=True),
    )

    # Migrate data back: take first element of array
    op.execute(
        """
        UPDATE properties
        SET proof_line = supporting_quotes[1]
        WHERE supporting_quotes IS NOT NULL AND array_length(supporting_quotes, 1) > 0
        """
    )

    # Drop the supporting_quotes column
    op.drop_column("properties", "supporting_quotes")

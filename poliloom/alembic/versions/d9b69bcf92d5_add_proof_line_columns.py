"""add_proof_line_columns

Revision ID: d9b69bcf92d5
Revises: ce33b2dac025
Create Date: 2025-07-17 11:21:44.743963

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9b69bcf92d5"
down_revision: Union[str, None] = "ce33b2dac025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add proof_line column to properties table
    op.add_column("properties", sa.Column("proof_line", sa.String(), nullable=True))

    # Add proof_line column to holds_position table
    op.add_column("holds_position", sa.Column("proof_line", sa.String(), nullable=True))

    # Add proof_line column to born_at table
    op.add_column("born_at", sa.Column("proof_line", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove proof_line column from born_at table
    op.drop_column("born_at", "proof_line")

    # Remove proof_line column from holds_position table
    op.drop_column("holds_position", "proof_line")

    # Remove proof_line column from properties table
    op.drop_column("properties", "proof_line")

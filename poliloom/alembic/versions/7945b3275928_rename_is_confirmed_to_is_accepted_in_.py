"""rename_is_confirmed_to_is_accepted_in_evaluations

Revision ID: 7945b3275928
Revises: 1bc6a146df39
Create Date: 2025-11-24 17:45:44.397903

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7945b3275928"
down_revision: Union[str, None] = "1bc6a146df39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("evaluations", "is_confirmed", new_column_name="is_accepted")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("evaluations", "is_accepted", new_column_name="is_confirmed")

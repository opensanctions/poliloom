"""Add P37 OFFICIAL_LANGUAGE to RelationType enum

Revision ID: ed4363cb43f2
Revises: 7eeea3e00d48
Create Date: 2025-09-17 17:13:51.570259

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ed4363cb43f2"
down_revision: Union[str, None] = "7eeea3e00d48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add P37 OFFICIAL_LANGUAGE to the RelationType enum
    op.execute("ALTER TYPE relationtype ADD VALUE 'OFFICIAL_LANGUAGE'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values
    # This would require recreating the enum entirely
    pass

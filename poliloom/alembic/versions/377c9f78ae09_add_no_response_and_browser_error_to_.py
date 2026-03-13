"""add no_response and browser_error to archivedpageerror enum

Revision ID: 377c9f78ae09
Revises: f5d737043dbe
Create Date: 2026-03-13 17:27:52.816844

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "377c9f78ae09"
down_revision: Union[str, None] = "f5d737043dbe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE archivedpageerror ADD VALUE 'NO_RESPONSE'")
    op.execute("ALTER TYPE archivedpageerror ADD VALUE 'BROWSER_ERROR'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL does not support removing values from an enum type.
    Recreating the enum would require migrating the column, which is
    handled by the parent migration's downgrade (drops the enum entirely).
    """

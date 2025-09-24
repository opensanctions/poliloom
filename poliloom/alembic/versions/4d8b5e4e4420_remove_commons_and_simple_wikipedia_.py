"""remove_commons_and_simple_wikipedia_links

Revision ID: 4d8b5e4e4420
Revises: ee5fe228aa1c
Create Date: 2025-09-24 20:22:34.565743

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4d8b5e4e4420"
down_revision: Union[str, None] = "ee5fe228aa1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove Wikipedia links for commons and simple Wikipedia."""
    # Remove commons and simple Wikipedia links
    op.execute("DELETE FROM wikipedia_links WHERE iso_code IN ('commons', 'simple')")


def downgrade() -> None:
    """Downgrade schema."""
    # Cannot restore deleted data, so this is a no-op
    pass

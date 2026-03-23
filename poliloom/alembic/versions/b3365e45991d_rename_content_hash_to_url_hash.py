"""rename content_hash to url_hash

Revision ID: b3365e45991d
Revises: 9c4cad19e007
Create Date: 2026-03-23 16:07:17.225173

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3365e45991d"
down_revision: Union[str, None] = "9c4cad19e007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("sources", "content_hash", new_column_name="url_hash")
    op.execute("ALTER INDEX ix_sources_content_hash RENAME TO ix_sources_url_hash")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("sources", "url_hash", new_column_name="content_hash")
    op.execute("ALTER INDEX ix_sources_url_hash RENAME TO ix_sources_content_hash")

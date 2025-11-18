"""add_official_website_to_wikipedia_projects

Revision ID: c0a6d8624a67
Revises: 7f45faa1f0df
Create Date: 2025-11-18 12:47:52.975439

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0a6d8624a67"
down_revision: Union[str, None] = "7f45faa1f0df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "wikipedia_projects", sa.Column("official_website", sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("wikipedia_projects", "official_website")

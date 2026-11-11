"""Remove official language relations.

Revision ID: 47bb98ef724e
Revises: 4944c37e9b32
Create Date: 2026-11-11 19:31:20.070192

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "47bb98ef724e"
down_revision: str | None = "4944c37e9b32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove existing P37 relations; new imports no longer track them."""
    op.execute(
        "DELETE FROM wikidata_relations WHERE relation_type = 'OFFICIAL_LANGUAGE'"
    )


def downgrade() -> None:
    """Deleted relations cannot be restored."""

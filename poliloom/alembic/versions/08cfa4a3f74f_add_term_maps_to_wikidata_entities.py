"""add term maps to wikidata_entities

Revision ID: 08cfa4a3f74f
Revises: 0858a2e5b2e2
Create Date: 2026-09-21 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "08cfa4a3f74f"
down_revision: str | None = "0858a2e5b2e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TERM_COLUMNS = ("labels", "descriptions", "aliases")


def upgrade() -> None:
    """Add language-keyed term map columns to wikidata_entities."""
    for column in TERM_COLUMNS:
        op.add_column(
            "wikidata_entities",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    """Drop term map columns from wikidata_entities."""
    for column in TERM_COLUMNS:
        op.drop_column("wikidata_entities", column)

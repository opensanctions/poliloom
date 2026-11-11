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
    """Stop tracking P37 and remove its existing relations."""
    op.execute(
        "DELETE FROM wikidata_relations WHERE relation_type = 'OFFICIAL_LANGUAGE'"
    )
    op.execute("ALTER TYPE relationtype RENAME TO relationtype_old")
    op.execute(
        """
        CREATE TYPE relationtype AS ENUM (
            'SUBCLASS_OF',
            'INSTANCE_OF',
            'PART_OF',
            'LOCATED_IN',
            'COUNTRY',
            'APPLIES_TO_JURISDICTION',
            'LANGUAGE_OF_WORK'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE wikidata_relations
        ALTER COLUMN relation_type TYPE relationtype
        USING relation_type::text::relationtype
        """
    )
    op.execute("DROP TYPE relationtype_old")


def downgrade() -> None:
    """Restore the P37 enum value; deleted relations cannot be restored."""
    op.execute("ALTER TYPE relationtype ADD VALUE 'OFFICIAL_LANGUAGE'")

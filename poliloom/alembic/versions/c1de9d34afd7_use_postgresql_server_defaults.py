"""use_postgresql_server_defaults

Revision ID: c1de9d34afd7
Revises: 5b8250938a3e
Create Date: 2025-08-26 18:20:14.494063

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c1de9d34afd7"
down_revision: Union[str, None] = "5b8250938a3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to use PostgreSQL server-side defaults."""
    # Update UUID columns to use gen_random_uuid()
    tables_with_uuid = [
        "property_evaluations",
        "position_evaluations",
        "birthplace_evaluations",
        "politicians",
        "archived_pages",
        "wikipedia_links",
        "properties",
        "countries",
        "locations",
        "positions",
        "holds_position",
        "born_at",
        "has_citizenship",
        "subclass_relations",
    ]

    for table in tables_with_uuid:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT gen_random_uuid()")

    # Update timestamp columns to use CURRENT_TIMESTAMP
    all_tables = tables_with_uuid + ["wikidata_classes"]

    for table in all_tables:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP"
        )


def downgrade() -> None:
    """Downgrade schema to remove PostgreSQL server-side defaults."""
    # Remove UUID defaults
    tables_with_uuid = [
        "property_evaluations",
        "position_evaluations",
        "birthplace_evaluations",
        "politicians",
        "archived_pages",
        "wikipedia_links",
        "properties",
        "countries",
        "locations",
        "positions",
        "holds_position",
        "born_at",
        "has_citizenship",
        "subclass_relations",
    ]

    for table in tables_with_uuid:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")

    # Remove timestamp defaults
    all_tables = tables_with_uuid + ["wikidata_classes"]

    for table in all_tables:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN created_at DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN updated_at DROP DEFAULT")

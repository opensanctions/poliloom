"""add postgresql triggers for updated_at columns

Revision ID: e6cee728924e
Revises: 2cac5a7c8d62
Create Date: 2025-08-29 15:59:31.322724

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e6cee728924e"
down_revision: Union[str, None] = "2cac5a7c8d62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# List of all tables with updated_at columns
TABLES_WITH_UPDATED_AT = [
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
    "wikidata_classes",
]


def upgrade() -> None:
    """Add PostgreSQL triggers for automatic updated_at timestamp updates."""

    # Create the trigger function that updates the updated_at column
    create_updated_at_function = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """

    op.execute(create_updated_at_function)

    # Create triggers for each table
    for table in TABLES_WITH_UPDATED_AT:
        trigger_sql = f"""
        CREATE TRIGGER trigger_update_{table}_updated_at
        BEFORE UPDATE ON {table}
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
        op.execute(trigger_sql)


def downgrade() -> None:
    """Remove PostgreSQL triggers for updated_at timestamp updates."""

    # Drop triggers for each table
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table}"
        )

    # Drop the trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

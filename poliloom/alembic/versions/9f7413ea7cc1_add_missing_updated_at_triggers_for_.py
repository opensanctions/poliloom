"""add missing updated_at triggers for wikidata_dumps, wikidata_entities, and wikidata_relations

Revision ID: 9f7413ea7cc1
Revises: 5537fc850c51
Create Date: 2025-09-24 14:06:23.750910

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f7413ea7cc1"
down_revision: Union[str, None] = "5537fc850c51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing updated_at triggers for tables that were missing them."""
    # Tables that need the updated_at trigger added
    missing_trigger_tables = [
        "wikidata_dumps",
        "wikidata_entities",
        "wikidata_relations",
    ]

    # Create triggers for each missing table
    for table in missing_trigger_tables:
        trigger_sql = f"""
        CREATE TRIGGER trigger_update_{table}_updated_at
        BEFORE UPDATE ON {table}
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
        op.execute(trigger_sql)


def downgrade() -> None:
    """Remove the added updated_at triggers."""
    # Tables that had triggers added
    added_trigger_tables = ["wikidata_dumps", "wikidata_entities", "wikidata_relations"]

    # Drop triggers for each table
    for table in added_trigger_tables:
        op.execute(
            f"DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table}"
        )

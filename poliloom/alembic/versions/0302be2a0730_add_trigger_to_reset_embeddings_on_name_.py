"""add trigger to reset embeddings on name change

Revision ID: 0302be2a0730
Revises: 146440e7d68e
Create Date: 2025-09-10 21:17:57.683955

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0302be2a0730"
down_revision: Union[str, None] = "146440e7d68e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION reset_embedding_on_name_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.name IS DISTINCT FROM NEW.name THEN
                -- Reset embedding for positions if the entity exists
                UPDATE positions SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
                -- Reset embedding for locations if the entity exists  
                UPDATE locations SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create the trigger
    op.execute("""
        CREATE TRIGGER wikidata_entity_name_change_trigger
            AFTER UPDATE ON wikidata_entities
            FOR EACH ROW
            EXECUTE FUNCTION reset_embedding_on_name_change();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the trigger
    op.execute(
        "DROP TRIGGER IF EXISTS wikidata_entity_name_change_trigger ON wikidata_entities;"
    )

    # Drop the function
    op.execute("DROP FUNCTION IF EXISTS reset_embedding_on_name_change();")

"""update_embedding_reset_trigger_positions_only

Revision ID: 3111e43b8ec0
Revises: f59dee05bf16
Create Date: 2025-10-09 11:38:04.827354

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3111e43b8ec0"
down_revision: Union[str, None] = "f59dee05bf16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update embedding reset trigger to only update positions table.

    Locations and countries now use pg_trgm fuzzy text search instead of embeddings,
    so we only need to reset embeddings for positions when their name changes.
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION reset_embedding_on_name_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.name IS DISTINCT FROM NEW.name THEN
                -- Reset embedding for positions if the entity exists
                -- (locations and countries use fuzzy text search, no embeddings)
                UPDATE positions SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Restore embedding reset trigger to update both positions and locations."""
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

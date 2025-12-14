"""remove embedding column from positions

Revision ID: b351d1ca5357
Revises: d6772e534c56
Create Date: 2025-12-14 15:30:55.249491

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = "b351d1ca5357"
down_revision: Union[str, None] = "d6772e534c56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the embedding reset trigger and function first
    op.execute(
        "DROP TRIGGER IF EXISTS wikidata_entity_name_change_trigger ON wikidata_entities"
    )
    op.execute("DROP FUNCTION IF EXISTS reset_embedding_on_name_change()")

    # Drop the embedding column
    op.drop_column("positions", "embedding")


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add the embedding column
    op.add_column(
        "positions",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=384),
            autoincrement=False,
            nullable=True,
        ),
    )

    # Re-create the embedding reset function and trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION reset_embedding_on_name_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.name IS DISTINCT FROM NEW.name THEN
                UPDATE positions SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER wikidata_entity_name_change_trigger
            AFTER UPDATE ON wikidata_entities
            FOR EACH ROW
            EXECUTE FUNCTION reset_embedding_on_name_change();
    """)

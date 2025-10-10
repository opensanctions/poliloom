"""refactor labels to separate table

Revision ID: ed77bf57de13
Revises: 3111e43b8ec0
Create Date: 2025-10-10 13:44:50.323094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ed77bf57de13'
down_revision: Union[str, None] = '3111e43b8ec0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create new table and indexes
    op.create_table('wikidata_entity_labels',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['wikidata_entities.wikidata_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_wikidata_entity_labels_entity_id', 'wikidata_entity_labels', ['entity_id'], unique=False)
    op.create_index('idx_wikidata_entity_labels_label_gin', 'wikidata_entity_labels', ['label'], unique=False, postgresql_using='gin', postgresql_ops={'label': 'gin_trgm_ops'})
    op.create_index('uq_wikidata_entity_labels_entity_label', 'wikidata_entity_labels', ['entity_id', 'label'], unique=True)

    # 2. Migrate data from array to separate table
    op.execute("""
        INSERT INTO wikidata_entity_labels (entity_id, label, created_at, updated_at)
        SELECT wikidata_id, unnest(labels), NOW(), NOW()
        FROM wikidata_entities
        WHERE labels IS NOT NULL AND array_length(labels, 1) > 0
    """)

    # 3. Drop old GIN index if it exists (from broken migration f59dee05bf16)
    op.execute("""
        DROP INDEX IF EXISTS idx_wikidata_entities_labels_gin
    """)

    # 4. Drop labels column
    op.drop_column('wikidata_entities', 'labels')


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Recreate labels column
    op.add_column('wikidata_entities', sa.Column('labels', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True))

    # 2. Migrate data back to array
    op.execute("""
        UPDATE wikidata_entities
        SET labels = subquery.labels_array
        FROM (
            SELECT entity_id, array_agg(label) as labels_array
            FROM wikidata_entity_labels
            GROUP BY entity_id
        ) AS subquery
        WHERE wikidata_entities.wikidata_id = subquery.entity_id
    """)

    # 3. Drop new table and indexes
    op.drop_index('uq_wikidata_entity_labels_entity_label', table_name='wikidata_entity_labels')
    op.drop_index('idx_wikidata_entity_labels_label_gin', table_name='wikidata_entity_labels', postgresql_using='gin', postgresql_ops={'label': 'gin_trgm_ops'})
    op.drop_index('idx_wikidata_entity_labels_entity_id', table_name='wikidata_entity_labels')
    op.drop_table('wikidata_entity_labels')

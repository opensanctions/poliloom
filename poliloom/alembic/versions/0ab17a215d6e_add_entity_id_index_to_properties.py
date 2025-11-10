"""add_entity_id_index_to_properties

Revision ID: 0ab17a215d6e
Revises: 250667def512
Create Date: 2025-11-05 19:41:02.515692

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0ab17a215d6e"
down_revision: Union[str, None] = "858e6436164d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for better query performance.

    - properties.entity_id: For queries filtering properties by entity_id
      (e.g., finding all birthplaces/positions referencing specific entities)
    - wikidata_relations.parent_entity_id: Critical for recursive hierarchy traversal
      (e.g., finding all descendants in subclass_of trees)
    """
    op.create_index("idx_properties_entity_id", "properties", ["entity_id"])
    op.create_index(
        "ix_wikidata_relations_parent_entity_id",
        "wikidata_relations",
        ["parent_entity_id"],
    )


def downgrade() -> None:
    """Remove indexes from properties and wikidata_relations tables."""
    op.drop_index(
        "ix_wikidata_relations_parent_entity_id", table_name="wikidata_relations"
    )
    op.drop_index("idx_properties_entity_id", table_name="properties")

"""fix wikidata_relations primary key to use statement_id

Revision ID: e61ba5f53b3f
Revises: 084925595654
Create Date: 2025-09-23 13:42:32.604075

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e61ba5f53b3f"
down_revision: Union[str, None] = "084925595654"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Truncate table since we can re-import the data
    op.execute("TRUNCATE TABLE wikidata_relations")

    # Drop the old primary key constraint
    op.drop_constraint("wikidata_relations_pkey", "wikidata_relations", type_="primary")

    # Drop the unique index on statement_id as it will become the primary key
    op.drop_index("uq_wikidata_relations_statement_id", table_name="wikidata_relations")

    # Add primary key constraint on statement_id
    op.create_primary_key(
        "wikidata_relations_pkey", "wikidata_relations", ["statement_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Truncate table
    op.execute("TRUNCATE TABLE wikidata_relations")

    # Drop the new primary key
    op.drop_constraint("wikidata_relations_pkey", "wikidata_relations", type_="primary")

    # Recreate the old primary key
    op.create_primary_key(
        "wikidata_relations_pkey",
        "wikidata_relations",
        ["parent_entity_id", "child_entity_id", "relation_type"],
    )

    # Recreate the unique index on statement_id
    op.create_index(
        "uq_wikidata_relations_statement_id",
        "wikidata_relations",
        ["statement_id"],
        unique=True,
    )

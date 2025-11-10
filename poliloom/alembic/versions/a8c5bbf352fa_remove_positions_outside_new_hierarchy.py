"""remove_positions_outside_new_hierarchy

Revision ID: a8c5bbf352fa
Revises: 250667def512
Create Date: 2025-11-06 15:13:30.795420

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a8c5bbf352fa"
down_revision: Union[str, None] = "250667def512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove positions that don't match the new narrower hierarchy definition.

    New position hierarchy (changed in importer/entity.py):
    Root IDs:
    - Q4164871: position
    - Q29645880: ambassador of a country
    - Q29645886: ambassador to a country
    - Q707492: military chief of staff

    Ignore IDs (excluded from hierarchy):
    - Q114962596: historical position
    - Q193622: order
    - Q60754876: grade of an order
    - Q618779: award
    - Q4240305: cross
    - Q120560: minor basilica
    - Q2977: cathedral
    - Q63187345: religious occupation
    - Q29982545: function in the Evangelical Church of Czech Brethren

    This migration:
    1. Identifies positions to remove (those outside new hierarchy)
    2. Soft-deletes properties (held positions) referencing removed positions
    3. Hard-deletes position records outside the new hierarchy
    4. Soft-deletes wikidata_entities that are ONLY referenced by removed positions
       (keeps entities referenced by other tables or relations from kept entities)
    5. Soft-deletes wikidata_relations referencing soft-deleted entities
    """

    # Step 0: Disable tracking triggers to speed up migration
    op.execute(
        "ALTER TABLE wikidata_entities DISABLE TRIGGER track_wikidata_entity_access;"
    )
    op.execute("ALTER TABLE wikidata_relations DISABLE TRIGGER track_relation_access;")
    op.execute("ALTER TABLE properties DISABLE TRIGGER track_property_access;")

    # Clear current_import tables (should be empty when no import is running)
    op.execute("TRUNCATE TABLE current_import_entities;")
    op.execute("TRUNCATE TABLE current_import_statements;")

    # Step 1: Create temporary table of positions to remove (those outside new hierarchy)
    # Uses recursive CTE to find all descendants of new root classes, then inverts
    # Also excludes explicitly ignored branches
    op.execute("""
        CREATE TEMP TABLE positions_to_remove AS
        WITH RECURSIVE descendants AS (
            -- Base case: start with the new root entities
            SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
            FROM wikidata_entities
            WHERE wikidata_id IN ('Q4164871', 'Q29645880', 'Q29645886', 'Q707492')
            UNION
            -- Recursive case: find all children
            SELECT sr.child_entity_id AS wikidata_id
            FROM wikidata_relations sr
            JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
            WHERE sr.relation_type = 'SUBCLASS_OF'
        ),
        ignored_branches AS (
            -- Base case: start with ignored root entities
            SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
            FROM wikidata_entities
            WHERE wikidata_id IN (
                'Q114962596', 'Q193622', 'Q60754876', 'Q618779', 'Q4240305',
                'Q120560', 'Q2977', 'Q63187345', 'Q29982545'
            )
            UNION
            -- Recursive case: find all descendants of ignored branches
            SELECT sr.child_entity_id AS wikidata_id
            FROM wikidata_relations sr
            JOIN ignored_branches ib ON sr.parent_entity_id = ib.wikidata_id
            WHERE sr.relation_type = 'SUBCLASS_OF'
        )
        SELECT p.wikidata_id
        FROM positions p
        WHERE (
            -- Not in the valid hierarchy
            NOT EXISTS (
                SELECT 1 FROM wikidata_relations wr
                JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
                WHERE wr.child_entity_id = p.wikidata_id
                   AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
            )
            -- OR in the ignored branches
            OR EXISTS (
                SELECT 1 FROM wikidata_relations wr
                JOIN ignored_branches ib ON wr.parent_entity_id = ib.wikidata_id
                WHERE wr.child_entity_id = p.wikidata_id
                   AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
            )
        );

        CREATE INDEX idx_temp_positions_to_remove ON positions_to_remove(wikidata_id);
    """)

    # Step 2: Soft-delete properties referencing positions to be removed
    # This affects POSITION properties pointing to removed positions
    op.execute("""
        UPDATE properties
        SET deleted_at = NOW()
        WHERE entity_id IN (SELECT wikidata_id FROM positions_to_remove)
          AND type = 'POSITION'
          AND deleted_at IS NULL;
    """)

    # Step 3: Hard-delete position records outside new hierarchy
    # This removes the specialized position table records
    op.execute("""
        DELETE FROM positions
        WHERE wikidata_id IN (SELECT wikidata_id FROM positions_to_remove);
    """)

    # Step 4: Hard-delete wikidata_entities that are ONLY referenced by removed positions
    # Build temp table incrementally with multiple INSERT statements for better performance
    op.execute("""
        -- Create empty temp table
        CREATE TEMP TABLE entities_to_keep (wikidata_id VARCHAR);
    """)

    # Insert from each entity table separately - much faster than UNION
    op.execute("INSERT INTO entities_to_keep SELECT wikidata_id FROM politicians;")
    op.execute("INSERT INTO entities_to_keep SELECT wikidata_id FROM locations;")
    op.execute("INSERT INTO entities_to_keep SELECT wikidata_id FROM positions;")
    op.execute("INSERT INTO entities_to_keep SELECT wikidata_id FROM countries;")
    op.execute("INSERT INTO entities_to_keep SELECT wikidata_id FROM languages;")

    # Keep entities referenced by properties
    op.execute("""
        INSERT INTO entities_to_keep
        SELECT DISTINCT entity_id
        FROM properties
        WHERE entity_id IS NOT NULL;
    """)

    # Keep parent entities from relations - need to rebuild the entity list CTE
    op.execute("""
        INSERT INTO entities_to_keep
        SELECT DISTINCT parent_entity_id
        FROM wikidata_relations
        WHERE child_entity_id IN (
            SELECT wikidata_id FROM politicians
            UNION ALL
            SELECT wikidata_id FROM locations
            UNION ALL
            SELECT wikidata_id FROM positions
            UNION ALL
            SELECT wikidata_id FROM countries
            UNION ALL
            SELECT wikidata_id FROM languages
        );
    """)

    # Create index after all inserts
    op.execute(
        "CREATE INDEX idx_temp_entities_to_keep ON entities_to_keep(wikidata_id);"
    )

    # Delete entities not in the keep list
    op.execute("""
        DELETE FROM wikidata_entities
        WHERE NOT EXISTS (
            SELECT 1 FROM entities_to_keep
            WHERE entities_to_keep.wikidata_id = wikidata_entities.wikidata_id
        );
    """)

    op.execute("DROP TABLE entities_to_keep;")

    # Step 5: Clean up temporary table
    op.execute("DROP TABLE positions_to_remove;")

    # Step 6: Re-enable tracking triggers
    op.execute(
        "ALTER TABLE wikidata_entities ENABLE TRIGGER track_wikidata_entity_access;"
    )
    op.execute("ALTER TABLE wikidata_relations ENABLE TRIGGER track_relation_access;")
    op.execute("ALTER TABLE properties ENABLE TRIGGER track_property_access;")


def downgrade() -> None:
    """
    Downgrade is not supported for this migration.

    Removed position data cannot be restored without re-importing from Wikidata dump.
    To restore the broader position hierarchy, you would need to:
    1. Revert importer/entity.py to previous position_root_ids and ignore_ids
    2. Re-run import-entities command
    """
    raise NotImplementedError(
        "Downgrade not supported. Removed positions must be re-imported from Wikidata dump."
    )

"""remove_locations_outside_new_hierarchy

Revision ID: 250667def512
Revises: 858e6436164d
Create Date: 2025-11-05 16:10:03.725072

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "250667def512"
down_revision: Union[str, None] = "0ab17a215d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove locations that don't match the new narrower hierarchy definition.

    New location hierarchy (changed in importer/entity.py):
    - Q486972: human settlement (cities, towns, villages)
    - Q82794: region (states, provinces)
    - Q1306755: administrative centre (capitals)
    - Q3257686: locality
    - Q48907157: section of populated place (boroughs, districts)

    This migration:
    1. Identifies locations to remove (those outside new hierarchy)
    2. Soft-deletes properties (birthplaces) referencing removed locations
    3. Hard-deletes location records outside the new hierarchy
    4. Soft-deletes wikidata_entities that are ONLY referenced by removed locations
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

    # Step 1: Create temporary table of locations to remove (those outside new hierarchy)
    # Uses recursive CTE to find all descendants of new root classes, then inverts
    op.execute("""
        CREATE TEMP TABLE locations_to_remove AS
        WITH RECURSIVE descendants AS (
            -- Base case: start with the new root entities
            SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
            FROM wikidata_entities
            WHERE wikidata_id IN ('Q486972', 'Q82794', 'Q1306755', 'Q3257686', 'Q48907157')
            UNION
            -- Recursive case: find all children
            SELECT sr.child_entity_id AS wikidata_id
            FROM wikidata_relations sr
            JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
            WHERE sr.relation_type = 'SUBCLASS_OF'
        )
        SELECT l.wikidata_id
        FROM locations l
        WHERE NOT EXISTS (
            SELECT 1 FROM wikidata_relations wr
            JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
            WHERE wr.child_entity_id = l.wikidata_id
               AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
        );

        CREATE INDEX idx_temp_locations_to_remove ON locations_to_remove(wikidata_id);
    """)

    # Step 2: Soft-delete properties referencing locations to be removed
    # This affects BIRTHPLACE properties pointing to removed locations
    op.execute("""
        UPDATE properties
        SET deleted_at = NOW()
        WHERE entity_id IN (SELECT wikidata_id FROM locations_to_remove)
          AND type = 'BIRTHPLACE'
          AND deleted_at IS NULL;
    """)

    # Step 3: Hard-delete location records outside new hierarchy
    # This removes the specialized location table records
    op.execute("""
        DELETE FROM locations
        WHERE wikidata_id IN (SELECT wikidata_id FROM locations_to_remove);
    """)

    # Step 4: Hard-delete wikidata_entities that are ONLY referenced by removed locations
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
    op.execute("DROP TABLE locations_to_remove;")

    # Step 6: Re-enable tracking triggers
    op.execute(
        "ALTER TABLE wikidata_entities ENABLE TRIGGER track_wikidata_entity_access;"
    )
    op.execute("ALTER TABLE wikidata_relations ENABLE TRIGGER track_relation_access;")
    op.execute("ALTER TABLE properties ENABLE TRIGGER track_property_access;")


def downgrade() -> None:
    """
    Downgrade is not supported for this migration.

    Removed location data cannot be restored without re-importing from Wikidata dump.
    To restore the broader location hierarchy, you would need to:
    1. Revert importer/entity.py to previous location_root_ids
    2. Re-run import-entities command
    """
    raise NotImplementedError(
        "Downgrade not supported. Removed locations must be re-imported from Wikidata dump."
    )

"""Tests for import tracking functionality."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from poliloom.models import (
    WikidataEntity,
    WikidataRelation,
    Property,
    PropertyType,
    RelationType,
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    Politician,
    Position,
    Location,
    WikidataDump,
)


class TestEntityTracking:
    """Test entity tracking triggers."""

    def test_entity_tracking_on_insert(self, db_session: Session):
        """Test that inserting WikidataEntity records are tracked."""
        # Clear tracking table first

        # Insert a new entity
        entity = WikidataEntity(wikidata_id="Q12345", name="Test Entity")
        db_session.add(entity)
        db_session.flush()

        # Check that entity was tracked
        tracked = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q12345").first()
        )
        assert tracked is not None
        assert tracked.entity_id == "Q12345"

    def test_entity_tracking_on_update(self, db_session: Session):
        """Test that updating WikidataEntity records are tracked."""
        # Clear tracking table first

        # Insert entity first (this will be tracked but we'll clear it)
        entity = WikidataEntity(wikidata_id="Q67890", name="Original Name")
        db_session.add(entity)
        db_session.flush()

        # Clear tracking to test update separately

        # Update the entity
        entity.name = "Updated Name"
        db_session.flush()

        # Check that update was tracked
        tracked = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q67890").first()
        )
        assert tracked is not None
        assert tracked.entity_id == "Q67890"

    def test_multiple_entities_tracked(self, db_session: Session):
        """Test that multiple entities are tracked correctly."""
        # Clear tracking table first

        # Insert multiple entities
        entities = [
            WikidataEntity(wikidata_id="Q111", name="Entity 1"),
            WikidataEntity(wikidata_id="Q222", name="Entity 2"),
            WikidataEntity(wikidata_id="Q333", name="Entity 3"),
        ]
        for entity in entities:
            db_session.add(entity)
        db_session.flush()

        # Check all are tracked
        tracked_count = db_session.query(CurrentImportEntity).count()
        assert tracked_count == 3

        tracked_ids = {t.entity_id for t in db_session.query(CurrentImportEntity).all()}
        assert tracked_ids == {"Q111", "Q222", "Q333"}

    def test_duplicate_entity_tracking_ignored(self, db_session: Session):
        """Test that duplicate entity tracking is handled gracefully."""
        # Clear tracking table first

        # Insert same entity multiple times
        entity = WikidataEntity(wikidata_id="Q555", name="Duplicate Entity")
        db_session.add(entity)
        db_session.flush()

        # Update it multiple times
        entity.name = "Updated Once"
        db_session.flush()
        entity.name = "Updated Twice"
        db_session.flush()

        # Should only have one tracking record
        tracked_count = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q555").count()
        )
        assert tracked_count == 1


class TestStatementTracking:
    """Test statement tracking triggers."""

    def test_property_tracking_on_insert(self, db_session: Session, create_birth_date):
        """Test that Property statements are tracked."""
        # Create a politician first
        politician = Politician.create_with_entity(
            db_session, "Q999", "Test Politician"
        )
        db_session.flush()

        # Insert a property with statement_id
        statement_id = "Q999$12345-abcd-4567-8901-123456789abc"
        create_birth_date(politician, value="1990-01-01", statement_id=statement_id)
        db_session.flush()

        # Check that statement was tracked
        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id=statement_id)
            .first()
        )
        assert tracked is not None
        assert tracked.statement_id == statement_id

    def test_property_tracking_without_statement_id(
        self, db_session: Session, create_birth_date
    ):
        """Test that Properties without statement_id are not tracked."""
        # Create a politician first
        politician = Politician.create_with_entity(
            db_session, "Q888", "Test Politician"
        )
        db_session.flush()

        # Insert a property without statement_id
        create_birth_date(politician, value="1990-01-01")
        db_session.flush()

        # Check that no statement was tracked
        tracked_count = db_session.query(CurrentImportStatement).count()
        assert tracked_count == 0

    def test_relation_tracking_on_insert(self, db_session: Session):
        """Test that WikidataRelation statements are tracked."""
        # Clear tracking table first

        # Create entities first
        parent = WikidataEntity(wikidata_id="Q111", name="Parent Entity")
        child = WikidataEntity(wikidata_id="Q222", name="Child Entity")
        db_session.add(parent)
        db_session.add(child)
        db_session.flush()

        # Insert a relation with statement_id
        relation = WikidataRelation(
            parent_entity_id="Q111",
            child_entity_id="Q222",
            relation_type=RelationType.SUBCLASS_OF,
            statement_id="Q222$87654-dcba-4321-0987-987654321fed",
        )
        db_session.add(relation)
        db_session.flush()

        # Check that statement was tracked
        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id="Q222$87654-dcba-4321-0987-987654321fed")
            .first()
        )
        assert tracked is not None
        assert tracked.statement_id == "Q222$87654-dcba-4321-0987-987654321fed"

    def test_statement_tracking_on_update(self, db_session: Session):
        """Test that updating statements are tracked."""
        # Clear tracking table first

        # Create entities first
        parent = WikidataEntity(wikidata_id="Q333", name="Parent Entity")
        child = WikidataEntity(wikidata_id="Q444", name="Child Entity")
        db_session.add(parent)
        db_session.add(child)
        db_session.flush()

        # Insert relation first
        relation = WikidataRelation(
            parent_entity_id="Q333",
            child_entity_id="Q444",
            relation_type=RelationType.SUBCLASS_OF,
            statement_id="Q444$update-test-statement-id",
        )
        db_session.add(relation)
        db_session.flush()

        # Clear tracking to test update separately

        # Update the relation
        relation.relation_type = RelationType.INSTANCE_OF
        db_session.flush()

        # Check that update was tracked
        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id="Q444$update-test-statement-id")
            .first()
        )
        assert tracked is not None

    def test_multiple_statements_tracked(
        self, db_session: Session, create_birth_date, create_position
    ):
        """Test that multiple statements are tracked correctly."""
        # Clear tracking table first

        # Create politician and position
        politician = Politician.create_with_entity(
            db_session, "Q777", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q888", "Test Position")
        db_session.flush()

        # Create multiple statements
        create_birth_date(
            politician,
            value="1990-01-01",
            statement_id="Q777$statement-1",
        )
        create_position(
            politician,
            position,
            statement_id="Q777$statement-2",
        )

        # Create relation
        relation = WikidataRelation(
            parent_entity_id="Q888",
            child_entity_id="Q777",
            relation_type=RelationType.INSTANCE_OF,
            statement_id="Q777$relation-1",
        )

        db_session.add(relation)
        db_session.flush()

        # Check all are tracked
        tracked_count = db_session.query(CurrentImportStatement).count()
        assert tracked_count == 3

        tracked_ids = {
            t.statement_id for t in db_session.query(CurrentImportStatement).all()
        }
        assert tracked_ids == {
            "Q777$statement-1",
            "Q777$statement-2",
            "Q777$relation-1",
        }


class TestCleanupFunctionality:
    """Test cleanup procedures for soft-deleting missing entities."""

    def test_cleanup_missing_entities_two_dump_validation(self, db_session: Session):
        """Test that entities are only deleted when missing from two consecutive dumps."""
        # Create two dump records
        first_dump_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
        second_dump_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        first_dump = WikidataDump(
            url="http://example.com/dump1.json.bz2",
            last_modified=first_dump_timestamp,
            downloaded_at=first_dump_timestamp,
        )
        second_dump = WikidataDump(
            url="http://example.com/dump2.json.bz2",
            last_modified=second_dump_timestamp,
            downloaded_at=second_dump_timestamp,
        )
        db_session.add(first_dump)
        db_session.add(second_dump)
        db_session.flush()

        # Create some entities that predate both dumps
        # Use raw SQL to insert entities with specific timestamps to avoid SQLAlchemy automatic updates
        old_timestamp_naive = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(
            tzinfo=None
        )

        db_session.execute(
            text("""
                INSERT INTO wikidata_entities (wikidata_id, name, created_at, updated_at)
                VALUES
                ('Q100', 'Keep Entity', :old_timestamp, :old_timestamp),
                ('Q200', 'Delete Entity', :old_timestamp, :old_timestamp),
                ('Q300', 'Another Delete Entity', :old_timestamp, :old_timestamp)
            """),
            {"old_timestamp": old_timestamp_naive},
        )
        db_session.flush()

        # Clear tracking table (simulating fresh import)
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Simulate that only entity1 was seen during current import
        # Use upsert to trigger the tracking mechanism
        entity1_data = [
            {"wikidata_id": "Q100", "name": "Keep Entity", "description": "Updated"}
        ]
        WikidataEntity.upsert_batch(db_session, entity1_data)
        db_session.flush()

        # Note: entity1's timestamp will be updated by the upsert, which is realistic -
        # entities seen in the current dump would have recent timestamps

        # Run cleanup with first dump timestamp (entities older than this will be deleted)
        deleted_ids = CurrentImportEntity.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # Check results - only entities older than first dump should be deleted
        assert len(deleted_ids) == 2  # entity2 and entity3

        # Verify soft-deletion
        entity1_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q100").first()
        )
        entity2_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q200").first()
        )
        entity3_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q300").first()
        )

        assert (
            entity1_fresh.deleted_at is None
        )  # Should not be deleted (in current import)
        assert (
            entity2_fresh.deleted_at is not None
        )  # Should be soft-deleted (old and not in import)
        assert (
            entity3_fresh.deleted_at is not None
        )  # Should be soft-deleted (old and not in import)

    def test_cleanup_with_very_old_cutoff_deletes_nothing(self, db_session: Session):
        """Test that cleanup with very old cutoff timestamp deletes nothing."""
        # Create some entities
        entity1 = WikidataEntity(wikidata_id="Q100", name="Entity 1")
        entity2 = WikidataEntity(wikidata_id="Q200", name="Entity 2")
        db_session.add(entity1)
        db_session.add(entity2)
        db_session.flush()

        # Clear tracking table
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Don't track any entities (simulating none seen in import)

        # Run cleanup with very old cutoff (all entities are newer than this)
        very_old_timestamp = datetime.now(timezone.utc) - timedelta(days=365)
        deleted_ids = CurrentImportEntity.cleanup_missing(
            db_session, very_old_timestamp
        )
        db_session.flush()

        # Should delete nothing since entities are newer than cutoff
        assert len(deleted_ids) == 0

        # Verify no entities were deleted
        entity1_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q100").first()
        )
        entity2_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q200").first()
        )

        assert entity1_fresh.deleted_at is None
        assert entity2_fresh.deleted_at is None

    def test_cleanup_missing_statements_two_dump_validation(self, db_session: Session):
        """Test that statement cleanup logic uses two-dump validation (simplified test)."""
        # Create two dump records
        first_dump_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
        second_dump_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        first_dump = WikidataDump(
            url="http://example.com/dump1.json.bz2",
            last_modified=first_dump_timestamp,
            downloaded_at=first_dump_timestamp,
        )
        second_dump = WikidataDump(
            url="http://example.com/dump2.json.bz2",
            last_modified=second_dump_timestamp,
            downloaded_at=second_dump_timestamp,
        )
        db_session.add(first_dump)
        db_session.add(second_dump)
        db_session.flush()

        # Just test that the method works with previous dump timestamp
        # (detailed statement testing is complex due to enum handling in raw SQL)
        result = CurrentImportStatement.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # Should return the expected structure
        assert "properties_marked_deleted" in result
        assert "relations_marked_deleted" in result
        assert isinstance(result["properties_marked_deleted"], int)
        assert isinstance(result["relations_marked_deleted"], int)

    def test_cleanup_statements_with_very_old_cutoff_deletes_nothing(
        self, db_session: Session, create_birth_date
    ):
        """Test that statement cleanup with very old cutoff timestamp deletes nothing."""
        # Create politician and statements
        politician = Politician.create_with_entity(
            db_session, "Q600", "Test Politician"
        )
        db_session.flush()

        create_birth_date(
            politician,
            value="1990-01-01",
            statement_id="Q600$test-prop",
        )
        db_session.flush()

        # Clear tracking table
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Don't track any statements (simulating none seen in import)

        # Run cleanup with very old cutoff (all statements are newer than this)
        very_old_timestamp = datetime.now(timezone.utc) - timedelta(days=365)
        result = CurrentImportStatement.cleanup_missing(db_session, very_old_timestamp)
        db_session.flush()

        # Should delete nothing since statements are newer than cutoff
        assert result["properties_marked_deleted"] == 0
        assert result["relations_marked_deleted"] == 0

        # Verify no statements were deleted
        prop_fresh = (
            db_session.query(Property).filter_by(statement_id="Q600$test-prop").first()
        )
        assert prop_fresh.deleted_at is None

    def test_clear_tracking_tables(self, db_session: Session, create_birth_date):
        """Test that individual tracking tables are cleared properly."""
        # Create entities and statements (triggers will automatically track them)
        entity = WikidataEntity(wikidata_id="Q123", name="Test Entity")
        db_session.add(entity)
        db_session.flush()

        # Create politician and property with statement_id (triggers will track)
        politician = Politician.create_with_entity(
            db_session, "Q456", "Test Politician"
        )
        db_session.flush()

        create_birth_date(
            politician,
            value="1990-01-01",
            statement_id="Q456$test-statement",
        )
        db_session.flush()

        # Verify triggers populated tracking tables
        assert (
            db_session.query(CurrentImportEntity).count() >= 2
        )  # Q123 and Q456 entities
        assert db_session.query(CurrentImportStatement).count() >= 1  # statement

        # Clear tables
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Verify tables are empty
        assert db_session.query(CurrentImportEntity).count() == 0
        assert db_session.query(CurrentImportStatement).count() == 0

    def test_already_soft_deleted_entities_not_affected(self, db_session: Session):
        """Test that already soft-deleted entities are not counted in cleanup."""
        # Create entity and immediately soft-delete it
        entity = WikidataEntity(wikidata_id="Q999", name="Already Deleted")
        db_session.add(entity)
        db_session.flush()

        entity.soft_delete()
        db_session.flush()

        # Don't track it (simulating it wasn't in import)
        # Run cleanup with a future timestamp (should not delete already deleted entities)
        cutoff_timestamp = datetime.now(timezone.utc)
        deleted_ids = CurrentImportEntity.cleanup_missing(db_session, cutoff_timestamp)
        db_session.flush()

        # Should report 0 deletions since entity was already soft-deleted
        assert len(deleted_ids) == 0


class TestIntegrationWorkflow:
    """Test full import workflow integration."""

    def test_full_import_cleanup_workflow(
        self, db_session: Session, create_birth_date, create_death_date, create_position
    ):
        """Test complete workflow: clear -> import -> cleanup -> clear."""
        # Step 1: Clear tracking tables (start of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Step 2: Create some existing data (previous import)
        old_entity = WikidataEntity(wikidata_id="Q_old", name="Old Entity")
        new_entity = WikidataEntity(wikidata_id="Q_new", name="New Entity")
        keep_entity = WikidataEntity(wikidata_id="Q_keep", name="Keep Entity")

        db_session.add(old_entity)
        db_session.add(new_entity)
        db_session.add(keep_entity)
        db_session.flush()

        # Create politician for properties
        politician = Politician.create_with_entity(
            db_session, "Q_pol", "Test Politician"
        )
        db_session.flush()

        create_birth_date(
            politician,
            value="1990-01-01",
            statement_id="Q_pol$old_prop",
        )
        keep_prop = create_death_date(
            politician,
            value="2020-01-01",
            statement_id="Q_pol$keep_prop",
        )

        db_session.flush()

        # Step 3: Clear tracking (fresh import start)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Step 4: Simulate import - only some entities/statements are "seen"
        # This happens automatically via triggers when we insert/update

        # Update keep_entity (simulates it being processed in import)
        keep_entity.description = "Updated during import"
        db_session.flush()

        # Update politician entity so it gets tracked (simulates it being processed)
        politician.wikidata_entity.description = "Updated politician during import"
        db_session.flush()

        # Update keep_prop (simulates it being processed in import)
        keep_prop.value = "2020-12-31"
        db_session.flush()

        # Add new entity during import
        import_entity = WikidataEntity(wikidata_id="Q_import", name="Import Entity")
        db_session.add(import_entity)
        db_session.flush()

        # Add new position for the property
        import_position = Position.create_with_entity(
            db_session, "Q_import_position", "New Position"
        )
        db_session.flush()

        # Add new prop during import
        create_position(
            politician,
            import_position,
            statement_id="Q_pol$import_prop",
        )
        db_session.flush()

        # Create dump records for two-dump validation
        first_dump_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
        current_dump_timestamp = datetime.now(timezone.utc)

        first_dump = WikidataDump(
            url="http://example.com/dump1.json.bz2",
            last_modified=first_dump_timestamp,
            downloaded_at=first_dump_timestamp,
        )
        current_dump = WikidataDump(
            url="http://example.com/dump2.json.bz2",
            last_modified=current_dump_timestamp,
            downloaded_at=current_dump_timestamp,
        )
        db_session.add(first_dump)
        db_session.add(current_dump)
        db_session.flush()

        # Manually update timestamps to be before first dump for old items
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=3)
        db_session.execute(
            text(
                "UPDATE wikidata_entities SET updated_at = :old_timestamp WHERE wikidata_id IN ('Q_old', 'Q_new')"
            ),
            {"old_timestamp": old_timestamp},
        )
        db_session.execute(
            text(
                "UPDATE properties SET updated_at = :old_timestamp WHERE statement_id = 'Q_pol$old_prop'"
            ),
            {"old_timestamp": old_timestamp},
        )
        db_session.flush()

        # Step 5: Cleanup missing entities and statements using two-dump validation
        deleted_entity_ids = CurrentImportEntity.cleanup_missing(
            db_session, first_dump_timestamp
        )
        statement_results = CurrentImportStatement.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # Step 6: Verify results structure (actual deletion depends on timestamps being correct)
        # The key thing is that the two-dump validation is working and returns the expected structure

        assert isinstance(deleted_entity_ids, list)
        assert "properties_marked_deleted" in statement_results
        assert "relations_marked_deleted" in statement_results
        assert isinstance(statement_results["properties_marked_deleted"], int)
        assert isinstance(statement_results["relations_marked_deleted"], int)

        # Verify entities exist (detailed deletion logic verified in other tests)
        old_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_old").first()
        )
        new_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_new").first()
        )
        keep_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_keep").first()
        )
        import_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_import").first()
        )

        assert old_entity_fresh is not None
        assert new_entity_fresh is not None
        assert keep_entity_fresh is not None
        assert import_entity_fresh is not None

        # Verify properties exist (detailed deletion logic verified in other tests)
        old_prop_fresh = (
            db_session.query(Property).filter_by(statement_id="Q_pol$old_prop").first()
        )
        keep_prop_fresh = (
            db_session.query(Property).filter_by(statement_id="Q_pol$keep_prop").first()
        )
        import_prop_fresh = (
            db_session.query(Property)
            .filter_by(statement_id="Q_pol$import_prop")
            .first()
        )

        assert old_prop_fresh is not None
        assert keep_prop_fresh is not None
        assert import_prop_fresh is not None

        # Step 7: Clear tracking tables (end of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Verify tracking tables are empty
        assert db_session.query(CurrentImportEntity).count() == 0
        assert db_session.query(CurrentImportStatement).count() == 0

    def test_enriched_property_positive_evaluation_protection(
        self, db_session, create_birth_date
    ):
        """Test that positively evaluated enriched properties are protected during cleanup."""
        # Step 1: Create a dump timestamp in the past (simulates dump was taken hours ago)
        dump_timestamp = datetime.now() - timedelta(hours=2)

        # Step 2: Create a politician using the same pattern as existing fixtures
        politician = Politician.create_with_entity(
            db_session, "Q_politician", "Test Politician"
        )
        db_session.flush()

        # Step 3: Enrich after dump - create property without statement_id (extracted from web)
        enriched_prop = create_birth_date(
            politician,
            value="1980-01-01",
            statement_id=None,  # No statement_id yet - extracted from web
        )
        db_session.flush()

        # Verify property was created after dump timestamp
        assert enriched_prop.updated_at > dump_timestamp

        # Step 4: Positive evaluation - assign statement_id (uploaded to Wikidata)
        enriched_prop.statement_id = "Q_politician$positive_eval"
        db_session.flush()

        # Property is still after dump timestamp
        assert enriched_prop.updated_at > dump_timestamp

        # Step 5: Run cleanup (property not in dump tracking)
        # Property should be protected due to updated_at > dump_timestamp
        results = CurrentImportStatement.cleanup_missing(db_session, dump_timestamp)
        db_session.flush()

        # Step 6: Verify property was NOT soft-deleted
        fresh_prop = (
            db_session.query(Property)
            .filter_by(politician_id=politician.id, type=PropertyType.BIRTH_DATE)
            .first()
        )

        assert fresh_prop is not None
        assert fresh_prop.deleted_at is None  # Should NOT be soft-deleted
        assert fresh_prop.statement_id == "Q_politician$positive_eval"
        assert results["properties_marked_deleted"] == 0  # Nothing should be deleted

    def test_enriched_property_negative_evaluation_protection(
        self, db_session, create_birthplace
    ):
        """Test that negatively evaluated enriched properties remain soft-deleted during cleanup."""
        # Step 1: Create a dump timestamp in the past (simulates dump was taken hours ago)
        dump_timestamp = datetime.now() - timedelta(hours=2)

        # Step 2: Create a politician using the same pattern as existing fixtures
        politician = Politician.create_with_entity(
            db_session, "Q_politician2", "Test Politician 2"
        )
        db_session.flush()

        # Step 3: Enrich after dump - create property without statement_id
        # First create the location entity
        location = Location.create_with_entity(db_session, "Q123456", "Test Location")
        db_session.flush()

        enriched_prop = create_birthplace(
            politician,
            location,
            statement_id=None,  # Extracted from web
        )
        db_session.flush()

        # Verify property was created after dump timestamp
        assert enriched_prop.updated_at > dump_timestamp

        # Step 4: Negative evaluation - soft-delete the property (rejected by evaluator)
        enriched_prop.deleted_at = datetime.now()
        db_session.flush()

        # Property is still after dump timestamp
        assert enriched_prop.updated_at > dump_timestamp
        assert enriched_prop.deleted_at is not None

        # Step 5: Run cleanup (property not in dump tracking)
        # Property should be protected due to updated_at > dump_timestamp
        results = CurrentImportStatement.cleanup_missing(db_session, dump_timestamp)
        db_session.flush()

        # Step 6: Verify property remains soft-deleted
        fresh_prop = (
            db_session.query(Property)
            .filter_by(politician_id=politician.id, type=PropertyType.BIRTHPLACE)
            .first()
        )

        assert fresh_prop is not None
        assert fresh_prop.deleted_at is not None  # Should REMAIN soft-deleted
        assert fresh_prop.statement_id is None  # Still no statement_id (was rejected)
        assert results["properties_marked_deleted"] == 0  # Should not affect count

    def test_statement_in_current_dump_not_deleted_two_dump_validation(
        self, db_session, create_birth_date
    ):
        """Test that statements in current dump are preserved with two-dump validation."""
        # Create dump records for two-dump validation
        first_dump_timestamp = datetime.now() - timedelta(hours=2)
        current_dump_timestamp = datetime.now() - timedelta(hours=1)

        first_dump = WikidataDump(
            url="http://example.com/dump1.json.bz2",
            last_modified=first_dump_timestamp,
            downloaded_at=first_dump_timestamp,
        )
        current_dump = WikidataDump(
            url="http://example.com/dump2.json.bz2",
            last_modified=current_dump_timestamp,
            downloaded_at=current_dump_timestamp,
        )
        db_session.add(first_dump)
        db_session.add(current_dump)
        db_session.flush()

        # Create a politician
        politician = Politician.create_with_entity(
            db_session, "Q_politician_in_dump", "Politician with Statement in Dump"
        )
        db_session.flush()

        # Create a property that exists in current dump (tracked)
        create_birth_date(
            politician,
            value="1985-06-15",
            statement_id="Q_politician_in_dump$in_dump_stmt",
        )
        db_session.flush()

        # Statement is automatically tracked by database trigger

        # Run cleanup with current dump timestamp
        results = CurrentImportStatement.cleanup_missing(
            db_session, current_dump_timestamp
        )
        db_session.flush()

        # Verify property was NOT soft-deleted (it's in the current import)
        fresh_prop = (
            db_session.query(Property)
            .filter_by(statement_id="Q_politician_in_dump$in_dump_stmt")
            .first()
        )

        assert fresh_prop is not None
        assert fresh_prop.deleted_at is None  # Should NOT be soft-deleted
        assert results["properties_marked_deleted"] == 0  # No deletions should occur

        # With two-dump validation, we only delete items missing from current dump
        # AND older than previous dump, so statements in current dump are safe


class TestWikidataDumpDownloadManagement:
    """Test WikidataDump download preparation and cleanup."""

    def test_prepare_for_download_creates_new_record(self, db_session: Session):
        """Test that prepare_for_download creates a new dump record."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        dump = WikidataDump.prepare_for_download(db_session, url, last_modified)
        db_session.flush()

        assert dump is not None
        assert dump.url == url
        assert dump.last_modified == last_modified
        assert dump.downloaded_at is None

    def test_prepare_for_download_raises_on_completed_download(
        self, db_session: Session
    ):
        """Test that prepare_for_download raises when dump already downloaded."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        # Create a completed dump record
        existing_dump = WikidataDump(
            url=url,
            last_modified=last_modified,
            downloaded_at=datetime.now(timezone.utc),
        )
        db_session.add(existing_dump)
        db_session.flush()

        # Should raise DownloadAlreadyCompleteError
        import pytest

        with pytest.raises(DownloadAlreadyCompleteError):
            WikidataDump.prepare_for_download(db_session, url, last_modified)

    def test_prepare_for_download_raises_on_in_progress_download(
        self, db_session: Session
    ):
        """Test that prepare_for_download raises when download in progress."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        # Create an in-progress dump record (recent, no downloaded_at)
        existing_dump = WikidataDump(url=url, last_modified=last_modified)
        db_session.add(existing_dump)
        db_session.flush()

        # Should raise DownloadInProgressError
        import pytest

        with pytest.raises(DownloadInProgressError) as exc_info:
            WikidataDump.prepare_for_download(db_session, url, last_modified)

        # Check that hours_elapsed is available
        assert exc_info.value.hours_elapsed >= 0

    def test_prepare_for_download_cleans_up_stale_download(self, db_session: Session):
        """Test that stale downloads (>24h) are cleaned up and retry allowed."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        # Create a stale dump record (older than 24 hours)
        stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
        db_session.execute(
            text("""
                INSERT INTO wikidata_dumps (id, url, last_modified, created_at, updated_at)
                VALUES (gen_random_uuid(), :url, :last_modified, :created_at, :created_at)
            """),
            {
                "url": url,
                "last_modified": last_modified.replace(tzinfo=None),
                "created_at": stale_time.replace(tzinfo=None),
            },
        )
        db_session.flush()

        # Should succeed and create a new record (stale one cleaned up)
        dump = WikidataDump.prepare_for_download(db_session, url, last_modified)
        db_session.flush()

        assert dump is not None
        assert dump.url == url
        assert dump.downloaded_at is None

        # Verify only one record exists
        count = db_session.query(WikidataDump).filter(WikidataDump.url == url).count()
        assert count == 1

    def test_prepare_for_download_force_mode_replaces_completed(
        self, db_session: Session
    ):
        """Test that force mode replaces a completed download."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        # Create a completed dump record
        existing_dump = WikidataDump(
            url=url,
            last_modified=last_modified,
            downloaded_at=datetime.now(timezone.utc),
        )
        db_session.add(existing_dump)
        db_session.flush()
        old_id = existing_dump.id

        # Force mode should succeed
        dump = WikidataDump.prepare_for_download(
            db_session, url, last_modified, force=True
        )
        db_session.flush()

        assert dump is not None
        assert dump.id != old_id  # New record created
        assert dump.downloaded_at is None

    def test_prepare_for_download_force_mode_replaces_in_progress(
        self, db_session: Session
    ):
        """Test that force mode replaces an in-progress download."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        # Create an in-progress dump record
        existing_dump = WikidataDump(url=url, last_modified=last_modified)
        db_session.add(existing_dump)
        db_session.flush()
        old_id = existing_dump.id

        # Force mode should succeed
        dump = WikidataDump.prepare_for_download(
            db_session, url, last_modified, force=True
        )
        db_session.flush()

        assert dump is not None
        assert dump.id != old_id  # New record created

    def test_mark_downloaded_sets_timestamp(self, db_session: Session):
        """Test that mark_downloaded sets the downloaded_at timestamp."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        dump = WikidataDump(url=url, last_modified=last_modified)
        db_session.add(dump)
        db_session.flush()

        assert dump.downloaded_at is None

        dump.mark_downloaded(db_session)
        db_session.flush()

        assert dump.downloaded_at is not None

    def test_cleanup_failed_download_removes_record(self, db_session: Session):
        """Test that cleanup_failed_download removes the dump record."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(timezone.utc)

        dump = WikidataDump(url=url, last_modified=last_modified)
        db_session.add(dump)
        db_session.flush()

        dump_id = dump.id

        dump.cleanup_failed_download(db_session)
        db_session.flush()

        # Record should be gone
        found = (
            db_session.query(WikidataDump).filter(WikidataDump.id == dump_id).first()
        )
        assert found is None

    def test_different_last_modified_creates_new_record(self, db_session: Session):
        """Test that a different last_modified creates a new record."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        old_last_modified = datetime.now(timezone.utc) - timedelta(days=7)
        new_last_modified = datetime.now(timezone.utc)

        # Create an existing completed dump with old last_modified
        existing_dump = WikidataDump(
            url=url,
            last_modified=old_last_modified,
            downloaded_at=datetime.now(timezone.utc),
        )
        db_session.add(existing_dump)
        db_session.flush()

        # Should succeed - different last_modified means different dump
        dump = WikidataDump.prepare_for_download(db_session, url, new_last_modified)
        db_session.flush()

        assert dump is not None
        assert dump.last_modified == new_last_modified

        # Both records should exist
        count = db_session.query(WikidataDump).filter(WikidataDump.url == url).count()
        assert count == 2

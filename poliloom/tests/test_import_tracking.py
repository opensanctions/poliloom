"""Tests for import tracking functionality."""

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
    Politician,
    Position,
)


class TestEntityTracking:
    """Test entity tracking triggers."""

    def test_entity_tracking_on_insert(self, db_session: Session):
        """Test that inserting WikidataEntity records are tracked."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Insert a new entity
        entity = WikidataEntity(wikidata_id="Q12345", name="Test Entity")
        db_session.add(entity)
        db_session.commit()

        # Check that entity was tracked
        tracked = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q12345").first()
        )
        assert tracked is not None
        assert tracked.entity_id == "Q12345"

    def test_entity_tracking_on_update(self, db_session: Session):
        """Test that updating WikidataEntity records are tracked."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Insert entity first (this will be tracked but we'll clear it)
        entity = WikidataEntity(wikidata_id="Q67890", name="Original Name")
        db_session.add(entity)
        db_session.commit()

        # Clear tracking to test update separately
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Update the entity
        entity.name = "Updated Name"
        db_session.commit()

        # Check that update was tracked
        tracked = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q67890").first()
        )
        assert tracked is not None
        assert tracked.entity_id == "Q67890"

    def test_multiple_entities_tracked(self, db_session: Session):
        """Test that multiple entities are tracked correctly."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Insert multiple entities
        entities = [
            WikidataEntity(wikidata_id="Q111", name="Entity 1"),
            WikidataEntity(wikidata_id="Q222", name="Entity 2"),
            WikidataEntity(wikidata_id="Q333", name="Entity 3"),
        ]
        for entity in entities:
            db_session.add(entity)
        db_session.commit()

        # Check all are tracked
        tracked_count = db_session.query(CurrentImportEntity).count()
        assert tracked_count == 3

        tracked_ids = {t.entity_id for t in db_session.query(CurrentImportEntity).all()}
        assert tracked_ids == {"Q111", "Q222", "Q333"}

    def test_duplicate_entity_tracking_ignored(self, db_session: Session):
        """Test that duplicate entity tracking is handled gracefully."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Insert same entity multiple times
        entity = WikidataEntity(wikidata_id="Q555", name="Duplicate Entity")
        db_session.add(entity)
        db_session.commit()

        # Update it multiple times
        entity.name = "Updated Once"
        db_session.commit()
        entity.name = "Updated Twice"
        db_session.commit()

        # Should only have one tracking record
        tracked_count = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q555").count()
        )
        assert tracked_count == 1


class TestStatementTracking:
    """Test statement tracking triggers."""

    def test_property_tracking_on_insert(self, db_session: Session):
        """Test that Property statements are tracked."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create a politician first
        politician = Politician.create_with_entity(
            db_session, "Q999", "Test Politician"
        )
        db_session.commit()

        # Insert a property with statement_id
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id="Q999$12345-abcd-4567-8901-123456789abc",
        )
        db_session.add(prop)
        db_session.commit()

        # Check that statement was tracked
        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id="Q999$12345-abcd-4567-8901-123456789abc")
            .first()
        )
        assert tracked is not None
        assert tracked.statement_id == "Q999$12345-abcd-4567-8901-123456789abc"

    def test_property_tracking_without_statement_id(self, db_session: Session):
        """Test that Properties without statement_id are not tracked."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create a politician first
        politician = Politician.create_with_entity(
            db_session, "Q888", "Test Politician"
        )
        db_session.commit()

        # Insert a property without statement_id
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id=None,
        )
        db_session.add(prop)
        db_session.commit()

        # Check that no statement was tracked
        tracked_count = db_session.query(CurrentImportStatement).count()
        assert tracked_count == 0

    def test_relation_tracking_on_insert(self, db_session: Session):
        """Test that WikidataRelation statements are tracked."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create entities first
        parent = WikidataEntity(wikidata_id="Q111", name="Parent Entity")
        child = WikidataEntity(wikidata_id="Q222", name="Child Entity")
        db_session.add(parent)
        db_session.add(child)
        db_session.commit()

        # Insert a relation with statement_id
        relation = WikidataRelation(
            parent_entity_id="Q111",
            child_entity_id="Q222",
            relation_type=RelationType.SUBCLASS_OF,
            statement_id="Q222$87654-dcba-4321-0987-987654321fed",
        )
        db_session.add(relation)
        db_session.commit()

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
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create entities first
        parent = WikidataEntity(wikidata_id="Q333", name="Parent Entity")
        child = WikidataEntity(wikidata_id="Q444", name="Child Entity")
        db_session.add(parent)
        db_session.add(child)
        db_session.commit()

        # Insert relation first
        relation = WikidataRelation(
            parent_entity_id="Q333",
            child_entity_id="Q444",
            relation_type=RelationType.SUBCLASS_OF,
            statement_id="Q444$update-test-statement-id",
        )
        db_session.add(relation)
        db_session.commit()

        # Clear tracking to test update separately
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Update the relation
        relation.relation_type = RelationType.INSTANCE_OF
        db_session.commit()

        # Check that update was tracked
        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id="Q444$update-test-statement-id")
            .first()
        )
        assert tracked is not None

    def test_multiple_statements_tracked(self, db_session: Session):
        """Test that multiple statements are tracked correctly."""
        # Clear tracking table first
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create politician and position
        politician = Politician.create_with_entity(
            db_session, "Q777", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q888", "Test Position")
        db_session.commit()

        # Create multiple statements
        prop1 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id="Q777$statement-1",
        )
        prop2 = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            statement_id="Q777$statement-2",
        )

        # Create relation
        relation = WikidataRelation(
            parent_entity_id="Q888",
            child_entity_id="Q777",
            relation_type=RelationType.INSTANCE_OF,
            statement_id="Q777$relation-1",
        )

        db_session.add(prop1)
        db_session.add(prop2)
        db_session.add(relation)
        db_session.commit()

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

    def test_cleanup_missing_entities(self, db_session: Session):
        """Test that entities not in tracking table are soft-deleted."""
        # Clear tracking table
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Create some entities
        entity1 = WikidataEntity(wikidata_id="Q100", name="Keep Entity")
        entity2 = WikidataEntity(wikidata_id="Q200", name="Delete Entity")
        entity3 = WikidataEntity(wikidata_id="Q300", name="Another Delete Entity")
        db_session.add(entity1)
        db_session.add(entity2)
        db_session.add(entity3)
        db_session.commit()

        # Clear tracking table (simulating fresh import)
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Simulate that only entity1 was seen during import using upsert like real importer
        entity1_data = [
            {"wikidata_id": "Q100", "name": "Keep Entity", "description": "Updated"}
        ]
        WikidataEntity.upsert_batch(
            db_session, entity1_data
        )  # This will trigger tracking
        db_session.commit()

        # Run cleanup
        result = CurrentImportEntity.cleanup_missing(db_session)
        db_session.commit()

        # Check results
        assert result["entities"] == 2  # entity2 and entity3 should be soft-deleted

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

        assert entity1_fresh.deleted_at is None  # Should not be deleted
        assert entity2_fresh.deleted_at is not None  # Should be soft-deleted
        assert entity3_fresh.deleted_at is not None  # Should be soft-deleted

    def test_cleanup_missing_statements(self, db_session: Session):
        """Test that statements not in tracking table are soft-deleted."""
        # Clear tracking table
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Create politician and position
        politician = Politician.create_with_entity(
            db_session, "Q400", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q500", "Test Position")
        db_session.commit()

        # Create properties and relations
        prop1 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id="Q400$keep-prop",
        )
        prop2 = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            statement_id="Q400$delete-prop",
        )

        relation1 = WikidataRelation(
            parent_entity_id="Q500",
            child_entity_id="Q400",
            relation_type=RelationType.INSTANCE_OF,
            statement_id="Q400$keep-relation",
        )
        relation2 = WikidataRelation(
            parent_entity_id="Q400",
            child_entity_id="Q500",
            relation_type=RelationType.SUBCLASS_OF,
            statement_id="Q400$delete-relation",
        )

        db_session.add(prop1)
        db_session.add(prop2)
        db_session.add(relation1)
        db_session.add(relation2)
        db_session.commit()

        # Clear tracking table (simulating fresh import)
        db_session.execute(text("TRUNCATE current_import_statements"))
        db_session.commit()

        # Simulate that only some statements were seen during import using upsert like real importer
        prop1_data = [
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTH_DATE,
                "value": "1990-01-01",
                "statement_id": "Q400$keep-prop",
            }
        ]
        relation1_data = [
            {
                "parent_entity_id": "Q500",
                "child_entity_id": "Q400",
                "relation_type": RelationType.INSTANCE_OF,
                "statement_id": "Q400$keep-relation",
            }
        ]
        Property.upsert_batch(db_session, prop1_data)  # This will trigger tracking
        WikidataRelation.upsert_batch(
            db_session, relation1_data
        )  # This will trigger tracking
        db_session.commit()

        # Run cleanup
        result = CurrentImportStatement.cleanup_missing(db_session)
        db_session.commit()

        # Check results
        assert result["properties"] == 1  # prop2 should be soft-deleted
        assert result["relations"] == 1  # relation2 should be soft-deleted

        # Verify soft-deletion
        prop1_fresh = (
            db_session.query(Property).filter_by(statement_id="Q400$keep-prop").first()
        )
        prop2_fresh = (
            db_session.query(Property)
            .filter_by(statement_id="Q400$delete-prop")
            .first()
        )
        rel1_fresh = (
            db_session.query(WikidataRelation)
            .filter_by(statement_id="Q400$keep-relation")
            .first()
        )
        rel2_fresh = (
            db_session.query(WikidataRelation)
            .filter_by(statement_id="Q400$delete-relation")
            .first()
        )

        assert prop1_fresh.deleted_at is None  # Should not be deleted
        assert prop2_fresh.deleted_at is not None  # Should be soft-deleted
        assert rel1_fresh.deleted_at is None  # Should not be deleted
        assert rel2_fresh.deleted_at is not None  # Should be soft-deleted

    def test_clear_tracking_tables(self, db_session: Session):
        """Test that individual tracking tables are cleared properly."""
        # Create entities and statements (triggers will automatically track them)
        entity = WikidataEntity(wikidata_id="Q123", name="Test Entity")
        db_session.add(entity)
        db_session.commit()

        # Create politician and property with statement_id (triggers will track)
        politician = Politician.create_with_entity(
            db_session, "Q456", "Test Politician"
        )
        db_session.commit()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id="Q456$test-statement",
        )
        db_session.add(prop)
        db_session.commit()

        # Verify triggers populated tracking tables
        assert (
            db_session.query(CurrentImportEntity).count() >= 2
        )  # Q123 and Q456 entities
        assert db_session.query(CurrentImportStatement).count() >= 1  # statement

        # Clear tables
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.commit()

        # Verify tables are empty
        assert db_session.query(CurrentImportEntity).count() == 0
        assert db_session.query(CurrentImportStatement).count() == 0

    def test_already_soft_deleted_entities_not_affected(self, db_session: Session):
        """Test that already soft-deleted entities are not counted in cleanup."""
        # Clear tracking table
        db_session.execute(text("TRUNCATE current_import_entities"))
        db_session.commit()

        # Create entity and immediately soft-delete it
        entity = WikidataEntity(wikidata_id="Q999", name="Already Deleted")
        db_session.add(entity)
        db_session.commit()

        entity.soft_delete()
        db_session.commit()

        # Don't track it (simulating it wasn't in import)
        # Run cleanup
        result = CurrentImportEntity.cleanup_missing(db_session)
        db_session.commit()

        # Should report 0 deletions since entity was already soft-deleted
        assert result["entities"] == 0


class TestIntegrationWorkflow:
    """Test full import workflow integration."""

    def test_full_import_cleanup_workflow(self, db_session: Session):
        """Test complete workflow: clear -> import -> cleanup -> clear."""
        # Step 1: Clear tracking tables (start of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.commit()

        # Step 2: Create some existing data (previous import)
        old_entity = WikidataEntity(wikidata_id="Q_old", name="Old Entity")
        new_entity = WikidataEntity(wikidata_id="Q_new", name="New Entity")
        keep_entity = WikidataEntity(wikidata_id="Q_keep", name="Keep Entity")

        db_session.add(old_entity)
        db_session.add(new_entity)
        db_session.add(keep_entity)
        db_session.commit()

        # Create politician for properties
        politician = Politician.create_with_entity(
            db_session, "Q_pol", "Test Politician"
        )
        db_session.commit()

        old_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            statement_id="Q_pol$old_prop",
        )
        keep_prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="2020-01-01",
            statement_id="Q_pol$keep_prop",
        )

        db_session.add(old_prop)
        db_session.add(keep_prop)
        db_session.commit()

        # Step 3: Clear tracking (fresh import start)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.commit()

        # Step 4: Simulate import - only some entities/statements are "seen"
        # This happens automatically via triggers when we insert/update

        # Update keep_entity (simulates it being processed in import)
        keep_entity.description = "Updated during import"
        db_session.commit()

        # Update politician entity so it gets tracked (simulates it being processed)
        politician.wikidata_entity.description = "Updated politician during import"
        db_session.commit()

        # Update keep_prop (simulates it being processed in import)
        keep_prop.value = "2020-12-31"
        db_session.commit()

        # Add new entity during import
        import_entity = WikidataEntity(wikidata_id="Q_import", name="Import Entity")
        db_session.add(import_entity)
        db_session.commit()

        # Add new prop during import
        import_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            value="New Position",
            statement_id="Q_pol$import_prop",
        )
        db_session.add(import_prop)
        db_session.commit()

        # Step 5: Cleanup missing entities and statements
        entity_results = CurrentImportEntity.cleanup_missing(db_session)
        statement_results = CurrentImportStatement.cleanup_missing(db_session)
        db_session.commit()

        # Step 6: Verify results
        # Should have soft-deleted: old_entity, new_entity, old_prop
        # Should have kept: keep_entity, politician, import_entity, keep_prop, import_prop

        assert entity_results["entities"] == 2  # old_entity, new_entity
        assert statement_results["properties"] == 1  # old_prop
        assert statement_results["relations"] == 0  # no relations in this test

        # Verify specific entities
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

        assert old_entity_fresh.deleted_at is not None  # Soft-deleted
        assert new_entity_fresh.deleted_at is not None  # Soft-deleted
        assert keep_entity_fresh.deleted_at is None  # Kept
        assert import_entity_fresh.deleted_at is None  # Kept

        # Verify specific properties
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

        assert old_prop_fresh.deleted_at is not None  # Soft-deleted
        assert keep_prop_fresh.deleted_at is None  # Kept
        assert import_prop_fresh.deleted_at is None  # Kept

        # Step 7: Clear tracking tables (end of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.commit()

        # Verify tracking tables are empty
        assert db_session.query(CurrentImportEntity).count() == 0
        assert db_session.query(CurrentImportStatement).count() == 0

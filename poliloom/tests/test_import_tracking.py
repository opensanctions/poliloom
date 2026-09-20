"""Tests for import tracking functionality."""

from datetime import UTC, datetime, timedelta

import orjson
from sqlalchemy import text
from sqlalchemy.orm import Session

from poliloom.models import (
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    Politician,
    RelationType,
    Statement,
    WikidataDump,
    WikidataEntity,
    WikidataRelation,
)

from .conftest import make_terms


def _statement_document(statement_id, property_id="P569"):
    """Minimal REST statement document for a time-valued statement."""
    return {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": property_id, "data_type": "time"},
        "value": {
            "type": "value",
            "content": {
                "time": "+1990-01-01T00:00:00Z",
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
        },
    }


def _add_statement(session, politician_id, statement_id, property_id="P569"):
    """Insert a statement via the ORM; the tracking trigger records it."""
    statement = Statement(
        politician_id=politician_id,
        document=_statement_document(statement_id, property_id),
    )
    session.add(statement)
    session.flush()
    return statement


def _add_old_statement(session, politician_id, statement_id, timestamp):
    """Insert a statement with explicit timestamps via raw SQL.

    The updated_at trigger overwrites UPDATEs, so statements predating a
    dump must be created with their timestamps set at INSERT time.
    """
    session.execute(
        text(
            """
            INSERT INTO statements (id, politician_id, document, created_at, updated_at)
            VALUES (
                gen_random_uuid(), :politician_id, CAST(:document AS jsonb),
                :timestamp, :timestamp
            )
        """
        ),
        {
            "politician_id": politician_id,
            "document": orjson.dumps(_statement_document(statement_id)).decode(),
            "timestamp": timestamp,
        },
    )
    session.flush()


def _add_old_relation(session, parent_id, child_id, statement_id, timestamp):
    """Insert a relation with explicit timestamps via raw SQL."""
    session.execute(
        text(
            """
            INSERT INTO wikidata_relations (
                statement_id, parent_entity_id, child_entity_id, relation_type,
                created_at, updated_at
            )
            VALUES (
                :statement_id, :parent_id, :child_id, 'SUBCLASS_OF'::relationtype,
                :timestamp, :timestamp
            )
        """
        ),
        {
            "statement_id": statement_id,
            "parent_id": parent_id,
            "child_id": child_id,
            "timestamp": timestamp,
        },
    )
    session.flush()


class TestEntityTracking:
    """Test entity tracking triggers."""

    def test_entity_tracking_on_insert(self, db_session: Session):
        """Test that inserting WikidataEntity records are tracked."""
        # Clear tracking table first

        # Insert a new entity
        entity = WikidataEntity(wikidata_id="Q12345")
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
        entity = WikidataEntity(wikidata_id="Q67890")
        db_session.add(entity)
        db_session.flush()

        # Clear tracking to test update separately

        # Update the entity
        entity.labels = {"en": "Updated Name"}
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
            WikidataEntity(wikidata_id="Q111"),
            WikidataEntity(wikidata_id="Q222"),
            WikidataEntity(wikidata_id="Q333"),
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
        entity = WikidataEntity(wikidata_id="Q555")
        db_session.add(entity)
        db_session.flush()

        # Update it multiple times
        entity.labels = {"en": "Updated Once"}
        db_session.flush()
        entity.labels = {"en": "Updated Twice"}
        db_session.flush()

        # Should only have one tracking record
        tracked_count = (
            db_session.query(CurrentImportEntity).filter_by(entity_id="Q555").count()
        )
        assert tracked_count == 1


class TestStatementTracking:
    """Test statement tracking triggers."""

    def test_statement_tracking_on_insert(self, db_session: Session):
        """Test that inserted statements are tracked by generated statement id."""
        politician = Politician.create_with_entity(
            db_session, "Q999", make_terms("Test Politician")
        )
        db_session.flush()

        statement_id = "Q999$12345-abcd-4567-8901-123456789abc"
        _add_statement(db_session, politician.id, statement_id)

        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id=statement_id)
            .first()
        )
        assert tracked is not None
        assert tracked.statement_id == statement_id

    def test_statement_tracking_on_update(self, db_session: Session):
        """Test that updating a statement document is tracked."""
        politician = Politician.create_with_entity(
            db_session, "Q998", make_terms("Test Politician")
        )
        db_session.flush()

        statement_id = "Q998$update-test-statement-id"
        statement = _add_statement(db_session, politician.id, statement_id)

        # Clear tracking to test update separately
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        updated_document = dict(statement.document)
        updated_document["rank"] = "preferred"
        statement.document = updated_document
        db_session.flush()

        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id=statement_id)
            .first()
        )
        assert tracked is not None

    def test_statement_tracking_via_upsert_batch(self, db_session: Session):
        """Test that the importer's upsert path tracks statements once."""
        politician = Politician.create_with_entity(
            db_session, "Q997", make_terms("Test Politician")
        )
        db_session.flush()

        statement_id = "Q997$upsert-test"
        row = {
            "politician_id": politician.id,
            "document": _statement_document(statement_id),
        }
        Statement.upsert_batch(db_session, [row])
        db_session.flush()

        tracked = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id=statement_id)
            .first()
        )
        assert tracked is not None

        # Re-importing the same statement must not duplicate tracking
        Statement.upsert_batch(db_session, [row])
        db_session.flush()

        tracked_count = (
            db_session.query(CurrentImportStatement)
            .filter_by(statement_id=statement_id)
            .count()
        )
        assert tracked_count == 1

    def test_relation_tracking_on_insert(self, db_session: Session):
        """Test that WikidataRelation statements are tracked."""
        # Clear tracking table first

        # Create entities first
        parent = WikidataEntity(wikidata_id="Q111")
        child = WikidataEntity(wikidata_id="Q222")
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

    def test_relation_tracking_on_update(self, db_session: Session):
        """Test that updating relations are tracked."""
        # Create entities first
        parent = WikidataEntity(wikidata_id="Q333")
        child = WikidataEntity(wikidata_id="Q444")
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
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

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

    def test_multiple_statements_tracked(self, db_session: Session):
        """Test that multiple statements and relations are tracked correctly."""
        politician = Politician.create_with_entity(
            db_session, "Q777", make_terms("Test Politician")
        )
        child = WikidataEntity(wikidata_id="Q888")
        db_session.add(child)
        db_session.flush()

        # Create multiple statements
        _add_statement(db_session, politician.id, "Q777$statement-1")
        _add_statement(db_session, politician.id, "Q777$statement-2")

        # Create relation
        relation = WikidataRelation(
            parent_entity_id="Q777",
            child_entity_id="Q888",
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
        first_dump_timestamp = datetime.now(UTC) - timedelta(hours=2)
        second_dump_timestamp = datetime.now(UTC) - timedelta(hours=1)

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
        old_timestamp_naive = (datetime.now(UTC) - timedelta(hours=3)).replace(
            tzinfo=None
        )

        db_session.execute(
            text("""
                INSERT INTO wikidata_entities (wikidata_id, created_at, updated_at)
                VALUES
                ('Q100', :old_timestamp, :old_timestamp),
                ('Q200', :old_timestamp, :old_timestamp),
                ('Q300', :old_timestamp, :old_timestamp)
            """),
            {"old_timestamp": old_timestamp_naive},
        )
        db_session.flush()

        # Clear tracking table (simulating fresh import)
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Simulate that only entity1 was seen during current import
        # Use upsert to trigger the tracking mechanism
        entity1_data = [{"wikidata_id": "Q100", "labels": {"en": "Keep Entity"}}]
        WikidataEntity.upsert_batch(db_session, entity1_data)
        db_session.flush()

        # Note: entity1's timestamp will be updated by the upsert, which is realistic -
        # entities seen in the current dump would have recent timestamps

        # Run cleanup with first dump timestamp (entities older than this will be deleted)
        deleted_count = CurrentImportEntity.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # Check results - only entities older than first dump should be deleted
        assert deleted_count == 2  # entity2 and entity3

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
        entity1 = WikidataEntity(wikidata_id="Q100")
        entity2 = WikidataEntity(wikidata_id="Q200")
        db_session.add(entity1)
        db_session.add(entity2)
        db_session.flush()

        # Clear tracking table
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Don't track any entities (simulating none seen in import)

        # Run cleanup with very old cutoff (all entities are newer than this)
        very_old_timestamp = datetime.now(UTC) - timedelta(days=365)
        deleted_count = CurrentImportEntity.cleanup_missing(
            db_session, very_old_timestamp
        )
        db_session.flush()

        # Should delete nothing since entities are newer than cutoff
        assert deleted_count == 0

        # Verify no entities were deleted
        entity1_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q100").first()
        )
        entity2_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q200").first()
        )

        assert entity1_fresh.deleted_at is None
        assert entity2_fresh.deleted_at is None

    def test_cleanup_missing_calls_delete_documents(
        self, db_session: Session, mock_search
    ):
        """Test that cleanup_missing deletes removed entities from the search index."""
        # Create entities with old timestamps
        entity1 = WikidataEntity(wikidata_id="Q100")
        entity2 = WikidataEntity(wikidata_id="Q200")
        db_session.add_all([entity1, entity2])
        db_session.flush()

        # Make entities old
        old_timestamp = datetime.now(UTC) - timedelta(days=30)
        db_session.execute(
            text("UPDATE wikidata_entities SET updated_at = :ts"),
            {"ts": old_timestamp},
        )
        db_session.flush()

        # Clear tracking table (simulating entities not seen in import)
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Run cleanup
        cutoff_timestamp = datetime.now(UTC)
        deleted_count = CurrentImportEntity.cleanup_missing(
            db_session, cutoff_timestamp
        )

        # Verify results
        assert deleted_count == 2
        mock_search.delete_documents.assert_called_once()
        assert set(mock_search.delete_documents.call_args.args[0]) == {"Q100", "Q200"}

    def test_cleanup_missing_does_not_call_delete_when_nothing_deleted(
        self, db_session: Session, mock_search
    ):
        """Test that delete_documents is not called when no entities are deleted."""
        # Create entities with recent timestamps
        entity1 = WikidataEntity(wikidata_id="Q100")
        db_session.add(entity1)
        db_session.flush()

        # Clear tracking table
        CurrentImportEntity.clear_tracking_table(db_session)
        db_session.flush()

        # Run cleanup with very old cutoff (nothing should be deleted)
        very_old_timestamp = datetime.now(UTC) - timedelta(days=365)
        deleted_count = CurrentImportEntity.cleanup_missing(
            db_session, very_old_timestamp
        )

        # Verify nothing was deleted
        assert deleted_count == 0
        mock_search.delete_documents.assert_not_called()

    def test_cleanup_missing_statements_two_dump_validation(self, db_session: Session):
        """Test statement and relation cleanup with two-dump validation.

        Statements missing from the current dump AND older than the previous
        dump are soft-deleted; tracked statements and statements newer than
        the previous dump are kept.
        """
        # Create two dump records
        first_dump_timestamp = datetime.now(UTC) - timedelta(hours=2)
        second_dump_timestamp = datetime.now(UTC) - timedelta(hours=1)

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

        politician = Politician.create_with_entity(
            db_session, "Q600", make_terms("Test Politician")
        )
        db_session.flush()

        parent = WikidataEntity(wikidata_id="Q601")
        child = WikidataEntity(wikidata_id="Q602")
        db_session.add(parent)
        db_session.add(child)
        db_session.flush()

        # Statements predating both dumps (from a previous import)
        old_timestamp_naive = (datetime.now(UTC) - timedelta(hours=3)).replace(
            tzinfo=None
        )
        _add_old_statement(
            db_session, politician.id, "Q600$delete-me", old_timestamp_naive
        )
        _add_old_statement(
            db_session, politician.id, "Q600$keep-tracked", old_timestamp_naive
        )
        # A relation predating both dumps and not seen in the current import
        _add_old_relation(
            db_session, "Q601", "Q602", "Q602$delete-relation", old_timestamp_naive
        )
        # A statement newer than the previous dump but not tracked
        # (added after the previous dump was taken)
        _add_statement(db_session, politician.id, "Q600$keep-recent")

        # Fresh import: only Q600$keep-tracked is seen again
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()
        Statement.upsert_batch(
            db_session,
            [
                {
                    "politician_id": politician.id,
                    "document": _statement_document("Q600$keep-tracked"),
                }
            ],
        )
        db_session.flush()

        result = CurrentImportStatement.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # The old untracked statement and relation are soft-deleted
        assert result["statements_marked_deleted"] == 1
        assert result["relations_marked_deleted"] == 1

        delete_me = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q600$delete-me")
            .first()
        )
        keep_tracked = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q600$keep-tracked")
            .first()
        )
        keep_recent = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q600$keep-recent")
            .first()
        )
        relation_fresh = (
            db_session.query(WikidataRelation)
            .filter_by(statement_id="Q602$delete-relation")
            .first()
        )

        assert delete_me.deleted_at is not None  # old and missing from dump
        assert keep_tracked.deleted_at is None  # seen in current import
        assert keep_recent.deleted_at is None  # newer than previous dump
        assert relation_fresh.deleted_at is not None  # old and missing from dump

    def test_cleanup_statements_with_very_old_cutoff_deletes_nothing(
        self, db_session: Session
    ):
        """Test that statement cleanup with very old cutoff timestamp deletes nothing."""
        politician = Politician.create_with_entity(
            db_session, "Q601", make_terms("Test Politician")
        )
        db_session.flush()

        _add_statement(db_session, politician.id, "Q601$test-statement")

        # Clear tracking table (simulating none seen in import)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Run cleanup with very old cutoff (all statements are newer than this)
        very_old_timestamp = datetime.now(UTC) - timedelta(days=365)
        result = CurrentImportStatement.cleanup_missing(db_session, very_old_timestamp)
        db_session.flush()

        # Should delete nothing since statements are newer than cutoff
        assert result["statements_marked_deleted"] == 0
        assert result["relations_marked_deleted"] == 0

        # Verify no statements were deleted
        statement_fresh = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q601$test-statement")
            .first()
        )
        assert statement_fresh.deleted_at is None

    def test_already_soft_deleted_statements_not_affected(self, db_session: Session):
        """Test that already soft-deleted statements are not counted in cleanup."""
        politician = Politician.create_with_entity(
            db_session, "Q602", make_terms("Test Politician")
        )
        db_session.flush()

        statement = _add_statement(db_session, politician.id, "Q602$already-deleted")
        statement.soft_delete()
        db_session.flush()

        # Don't track it (simulating it wasn't in import)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Run cleanup with a future timestamp
        cutoff_timestamp = datetime.now(UTC)
        result = CurrentImportStatement.cleanup_missing(db_session, cutoff_timestamp)
        db_session.flush()

        # Should report 0 deletions since the statement was already soft-deleted
        assert result["statements_marked_deleted"] == 0

    def test_clear_tracking_tables(self, db_session: Session):
        """Test that individual tracking tables are cleared properly."""
        # Create entities and statements (triggers will automatically track them)
        entity = WikidataEntity(wikidata_id="Q123")
        db_session.add(entity)
        db_session.flush()

        politician = Politician.create_with_entity(
            db_session, "Q456", make_terms("Test Politician")
        )
        db_session.flush()

        _add_statement(db_session, politician.id, "Q456$test-statement")

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
        entity = WikidataEntity(wikidata_id="Q999")
        db_session.add(entity)
        db_session.flush()

        entity.soft_delete()
        db_session.flush()

        # Don't track it (simulating it wasn't in import)
        # Run cleanup with a future timestamp (should not delete already deleted entities)
        cutoff_timestamp = datetime.now(UTC)
        deleted_count = CurrentImportEntity.cleanup_missing(
            db_session, cutoff_timestamp
        )
        db_session.flush()

        # Should report 0 deletions since entity was already soft-deleted
        assert deleted_count == 0


class TestIntegrationWorkflow:
    """Test full import workflow integration."""

    def test_full_import_cleanup_workflow(self, db_session: Session):
        """Test complete workflow: clear -> import -> cleanup -> clear."""
        # Step 1: Clear tracking tables (start of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Step 2: Create data from a previous import. Old rows are inserted
        # with raw SQL because the updated_at trigger overwrites UPDATEs.
        old_timestamp_naive = (datetime.now(UTC) - timedelta(hours=3)).replace(
            tzinfo=None
        )
        db_session.execute(
            text(
                """
                INSERT INTO wikidata_entities (wikidata_id, created_at, updated_at)
                VALUES
                ('Q_old', :old_timestamp, :old_timestamp),
                ('Q_keep', :old_timestamp, :old_timestamp)
            """
            ),
            {"old_timestamp": old_timestamp_naive},
        )
        db_session.flush()

        politician = Politician.create_with_entity(
            db_session, "Q_pol", make_terms("Test Politician")
        )
        db_session.flush()

        # Statements predating the first dump
        first_dump_timestamp = datetime.now(UTC) - timedelta(hours=2)
        _add_old_statement(
            db_session, politician.id, "Q_pol$old_stmt", old_timestamp_naive
        )
        _add_old_statement(
            db_session, politician.id, "Q_pol$keep_stmt", old_timestamp_naive
        )

        # Step 3: Clear tracking (fresh import start)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Step 4: Simulate the current import - only some data is seen again
        # (upserts fire the tracking triggers and refresh updated_at)
        keep_entity = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_keep").one()
        )
        keep_entity.labels = {"en": "Keep Entity (updated)"}
        db_session.flush()

        politician.wikidata_entity.labels = {"en": "Test Politician (updated)"}
        db_session.flush()

        Statement.upsert_batch(
            db_session,
            [
                {
                    "politician_id": politician.id,
                    "document": _statement_document("Q_pol$keep_stmt"),
                },
                {
                    "politician_id": politician.id,
                    "document": _statement_document("Q_pol$import_stmt"),
                },
            ],
        )
        db_session.flush()

        # Create dump records for two-dump validation
        current_dump_timestamp = datetime.now(UTC)
        current_dump = WikidataDump(
            url="http://example.com/dump2.json.bz2",
            last_modified=current_dump_timestamp,
            downloaded_at=current_dump_timestamp,
        )
        db_session.add(current_dump)
        db_session.flush()

        # Step 5: Cleanup missing entities and statements using two-dump validation
        deleted_entity_count = CurrentImportEntity.cleanup_missing(
            db_session, first_dump_timestamp
        )
        statement_results = CurrentImportStatement.cleanup_missing(
            db_session, first_dump_timestamp
        )
        db_session.flush()

        # Q_old was not seen in the current import and predates the first dump
        assert deleted_entity_count == 1

        # Q_pol$old_stmt was not seen in the current import and predates the
        # first dump; the re-imported and newly imported statements survive
        assert statement_results["statements_marked_deleted"] == 1
        assert statement_results["relations_marked_deleted"] == 0

        old_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_old").first()
        )
        keep_entity_fresh = (
            db_session.query(WikidataEntity).filter_by(wikidata_id="Q_keep").first()
        )
        assert old_entity_fresh.deleted_at is not None
        assert keep_entity_fresh.deleted_at is None

        old_stmt_fresh = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q_pol$old_stmt")
            .first()
        )
        keep_stmt_fresh = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q_pol$keep_stmt")
            .first()
        )
        import_stmt_fresh = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q_pol$import_stmt")
            .first()
        )
        assert old_stmt_fresh.deleted_at is not None
        assert keep_stmt_fresh.deleted_at is None
        assert import_stmt_fresh.deleted_at is None

        # Step 6: Clear tracking tables (end of import)
        CurrentImportEntity.clear_tracking_table(db_session)
        CurrentImportStatement.clear_tracking_table(db_session)
        db_session.flush()

        # Verify tracking tables are empty
        assert db_session.query(CurrentImportEntity).count() == 0
        assert db_session.query(CurrentImportStatement).count() == 0

    def test_statement_in_current_dump_not_deleted_two_dump_validation(
        self, db_session: Session
    ):
        """Test that statements in current dump are preserved with two-dump validation."""
        # Create dump records for two-dump validation
        first_dump_timestamp = datetime.now(UTC) - timedelta(hours=2)
        current_dump_timestamp = datetime.now(UTC) - timedelta(hours=1)

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
            db_session,
            "Q_politician_in_dump",
            make_terms("Politician with Statement in Dump"),
        )
        db_session.flush()

        # Create a statement that exists in current dump (tracked)
        _add_statement(db_session, politician.id, "Q_politician_in_dump$in_dump_stmt")

        # Statement is automatically tracked by database trigger

        # Run cleanup with current dump timestamp
        results = CurrentImportStatement.cleanup_missing(
            db_session, current_dump_timestamp
        )
        db_session.flush()

        # Verify statement was NOT soft-deleted (it's in the current import)
        fresh_statement = (
            db_session.query(Statement)
            .filter_by(wikidata_statement_id="Q_politician_in_dump$in_dump_stmt")
            .first()
        )

        assert fresh_statement is not None
        assert fresh_statement.deleted_at is None  # Should NOT be soft-deleted
        assert results["statements_marked_deleted"] == 0  # No deletions should occur

        # With two-dump validation, we only delete items missing from current dump
        # AND older than previous dump, so statements in current dump are safe


class TestWikidataDumpDownloadManagement:
    """Test WikidataDump download preparation and cleanup."""

    def test_prepare_for_download_creates_new_record(self, db_session: Session):
        """Test that prepare_for_download creates a new dump record."""
        url = "https://dumps.wikimedia.org/test.json.bz2"
        last_modified = datetime.now(UTC)

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
        last_modified = datetime.now(UTC)

        # Create a completed dump record
        existing_dump = WikidataDump(
            url=url,
            last_modified=last_modified,
            downloaded_at=datetime.now(UTC),
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
        last_modified = datetime.now(UTC)

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
        last_modified = datetime.now(UTC)

        # Create a stale dump record (older than 24 hours)
        stale_time = datetime.now(UTC) - timedelta(hours=25)
        db_session.execute(
            text("""
                INSERT INTO wikidata_dumps (id, url, last_modified, created_at, updated_at)
                VALUES (gen_random_uuid(), :url, :last_modified, :created_at, :created_at)
            """),
            {
                "url": url,
                "last_modified": last_modified,
                "created_at": stale_time,
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
        last_modified = datetime.now(UTC)

        # Create a completed dump record
        existing_dump = WikidataDump(
            url=url,
            last_modified=last_modified,
            downloaded_at=datetime.now(UTC),
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
        last_modified = datetime.now(UTC)

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
        last_modified = datetime.now(UTC)

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
        last_modified = datetime.now(UTC)

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
        old_last_modified = datetime.now(UTC) - timedelta(days=7)
        new_last_modified = datetime.now(UTC)

        # Create an existing completed dump with old last_modified
        existing_dump = WikidataDump(
            url=url,
            last_modified=old_last_modified,
            downloaded_at=datetime.now(UTC),
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

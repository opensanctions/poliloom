"""Tests for WikidataHierarchyImporter."""

from poliloom.models import WikidataEntity, WikidataRelation


class TestWikidataHierarchyImporter:
    """Test hierarchy importing functionality."""

    def test_upsert_wikidata_entities_batch(self, db_session):
        """Test upserting a batch of WikidataEntity records."""
        entities = [
            {"wikidata_id": "Q1", "name": "Entity 1"},
            {"wikidata_id": "Q2", "name": "Entity 2"},
        ]

        WikidataEntity.upsert_batch(db_session, entities)

        # Verify entities were inserted
        inserted_entities = db_session.query(WikidataEntity).all()
        assert len(inserted_entities) == 2
        wikidata_ids = {e.wikidata_id for e in inserted_entities}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_upsert_wikidata_entities_batch_with_duplicates(self, db_session):
        """Test upserting WikidataEntity batch with duplicates."""
        # Insert initial batch
        initial_entities = [
            {"wikidata_id": "Q1", "name": "Entity 1"},
            {"wikidata_id": "Q2", "name": "Entity 2"},
        ]
        WikidataEntity.upsert_batch(db_session, initial_entities)

        # Upsert batch with some duplicates and new items
        entities_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "name": "Entity 1 Updated",
            },  # Duplicate (should update)
            {"wikidata_id": "Q3", "name": "Entity 3"},  # New
        ]
        WikidataEntity.upsert_batch(db_session, entities_with_duplicates)

        # Verify all entities exist with correct data
        inserted_entities = db_session.query(WikidataEntity).all()
        assert len(inserted_entities) == 3
        wikidata_ids = {e.wikidata_id for e in inserted_entities}
        assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Verify Q1 was updated
        q1_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q1")
            .first()
        )
        assert q1_entity.name == "Entity 1 Updated"

    def test_upsert_wikidata_entities_batch_empty(self, db_session):
        """Test upserting empty batch of WikidataEntity records."""
        # Should handle empty batch gracefully without errors
        WikidataEntity.upsert_batch(db_session, [])

        # Verify no entities were inserted
        inserted_entities = db_session.query(WikidataEntity).all()
        assert len(inserted_entities) == 0

    def test_upsert_wikidata_relations_batch(self, db_session):
        """Test upserting a batch of WikidataRelation records."""
        # Create parent entities first
        parent_entity = WikidataEntity(wikidata_id="Q1", name="Parent Entity")
        child_entity = WikidataEntity(wikidata_id="Q2", name="Child Entity")
        db_session.add_all([parent_entity, child_entity])
        db_session.flush()

        # Upsert relations
        relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "relation_type": "SUBCLASS_OF",
                "statement_id": "Q2$statement-1",
            },
        ]
        WikidataRelation.upsert_batch(db_session, relations)

        # Verify relations were inserted
        inserted_relations = db_session.query(WikidataRelation).all()
        assert len(inserted_relations) == 1
        assert inserted_relations[0].parent_entity_id == "Q1"
        assert inserted_relations[0].child_entity_id == "Q2"

    def test_upsert_wikidata_relations_batch_with_duplicates(self, db_session):
        """Test upserting WikidataRelation batch with duplicates."""
        # Create parent entities
        parent_entity = WikidataEntity(wikidata_id="Q1", name="Parent Entity")
        child1_entity = WikidataEntity(wikidata_id="Q2", name="Child Entity 1")
        child2_entity = WikidataEntity(wikidata_id="Q3", name="Child Entity 2")
        db_session.add_all([parent_entity, child1_entity, child2_entity])
        db_session.flush()

        # Upsert initial relations
        initial_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "relation_type": "SUBCLASS_OF",
                "statement_id": "Q2$statement-1",
            },
        ]
        WikidataRelation.upsert_batch(db_session, initial_relations)

        # Upsert again with duplicates and new items
        relations_with_duplicates = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "relation_type": "INSTANCE_OF",  # Different relation type for same statement
                "statement_id": "Q2$statement-1",
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q3",
                "relation_type": "SUBCLASS_OF",
                "statement_id": "Q3$statement-1",
            },
        ]
        WikidataRelation.upsert_batch(db_session, relations_with_duplicates)

        # Verify all relations exist
        inserted_relations = db_session.query(WikidataRelation).all()
        assert len(inserted_relations) == 2
        statement_ids = {r.statement_id for r in inserted_relations}
        assert statement_ids == {"Q2$statement-1", "Q3$statement-1"}

        # Verify Q2$statement-1 was updated to INSTANCE_OF
        q2_relation = (
            db_session.query(WikidataRelation)
            .filter(WikidataRelation.statement_id == "Q2$statement-1")
            .first()
        )
        assert q2_relation.relation_type.name == "INSTANCE_OF"

    def test_upsert_wikidata_relations_batch_empty(self, db_session):
        """Test upserting empty batch of WikidataRelation records."""
        # Should handle empty batch gracefully without errors
        WikidataRelation.upsert_batch(db_session, [])

        # Verify no relations were inserted
        inserted_relations = db_session.query(WikidataRelation).all()
        assert len(inserted_relations) == 0

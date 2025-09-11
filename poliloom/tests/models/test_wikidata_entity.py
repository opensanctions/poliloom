"""Tests for WikidataEntity model."""

from sqlalchemy.dialects.postgresql import insert

from poliloom.models import WikidataEntity, WikidataRelation, RelationType


class TestWikidataEntity:
    """Test WikidataEntity model functionality."""

    def test_query_hierarchy_descendants(self, db_session):
        """Test querying all descendants in a hierarchy."""
        # Set up test hierarchy in database: Q1 -> Q2 -> Q3, Q1 -> Q4
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Child 1"},
            {"wikidata_id": "Q3", "name": "Grandchild"},
            {"wikidata_id": "Q4", "name": "Child 2"},
        ]

        test_relations = [
            {"parent_entity_id": "Q1", "child_entity_id": "Q2"},
            {"parent_entity_id": "Q2", "child_entity_id": "Q3"},
            {"parent_entity_id": "Q1", "child_entity_id": "Q4"},
        ]

        # Insert test data
        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["parent_entity_id", "child_entity_id", "relation_type"]
        )
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants
        descendants = WikidataEntity.query_hierarchy_descendants(db_session, ["Q1"])

        # Should include Q1 itself and all its descendants with names
        assert descendants == {"Q1", "Q2", "Q3", "Q4"}

    def test_query_hierarchy_descendants_single_node(self, db_session):
        """Test querying descendants for a single node with no children."""
        # Set up single node
        test_classes = [{"wikidata_id": "Q1", "name": "Single Node"}]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants
        descendants = WikidataEntity.query_hierarchy_descendants(db_session, ["Q1"])

        # Should only include Q1 itself
        assert descendants == {"Q1"}

    def test_query_hierarchy_descendants_partial_tree(self, db_session):
        """Test querying descendants for a subtree in a larger hierarchy."""
        # Create larger hierarchy: Q1 -> {Q2, Q3}, Q2 -> {Q4, Q5}
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Branch"},
            {"wikidata_id": "Q3", "name": "Leaf 1"},
            {"wikidata_id": "Q4", "name": "Leaf 2"},
            {"wikidata_id": "Q5", "name": "Leaf 3"},
        ]

        test_relations = [
            {"parent_entity_id": "Q1", "child_entity_id": "Q2"},
            {"parent_entity_id": "Q1", "child_entity_id": "Q3"},
            {"parent_entity_id": "Q2", "child_entity_id": "Q4"},
            {"parent_entity_id": "Q2", "child_entity_id": "Q5"},
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["parent_entity_id", "child_entity_id", "relation_type"]
        )
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants of Q2 (should include Q2, Q4, Q5)
        descendants = WikidataEntity.query_hierarchy_descendants(db_session, ["Q2"])
        assert descendants == {"Q2", "Q4", "Q5"}

        # Test querying descendants of Q3 (should only include Q3)
        descendants_q3 = WikidataEntity.query_hierarchy_descendants(db_session, ["Q3"])
        assert descendants_q3 == {"Q3"}

    def test_query_hierarchy_descendants_with_relation_type(self, db_session):
        """Test querying descendants with a specific relation type."""
        # Set up test hierarchy with different relation types
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Child"},
            {"wikidata_id": "Q3", "name": "Instance"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "relation_type": RelationType.SUBCLASS_OF,
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q3",
                "relation_type": RelationType.INSTANCE_OF,
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["parent_entity_id", "child_entity_id", "relation_type"]
        )
        db_session.execute(stmt)
        db_session.commit()

        # Test querying with SUBCLASS_OF relation type (default)
        descendants_subclass = WikidataEntity.query_hierarchy_descendants(
            db_session, ["Q1"]
        )
        assert descendants_subclass == {"Q1", "Q2"}

        # Test querying with INSTANCE_OF relation type
        descendants_instance = WikidataEntity.query_hierarchy_descendants(
            db_session, ["Q1"], relation_type=RelationType.INSTANCE_OF
        )
        assert descendants_instance == {"Q1", "Q3"}

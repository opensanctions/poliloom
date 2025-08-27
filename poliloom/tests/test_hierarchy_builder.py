"""Tests for HierarchyBuilder."""

import pytest
from sqlalchemy.dialects.postgresql import insert

from poliloom.models import WikidataClass
from poliloom.services.hierarchy_builder import HierarchyBuilder


class TestHierarchyBuilder:
    """Test HierarchyBuilder functionality."""

    @pytest.fixture
    def builder(self, db_session):
        """Create a HierarchyBuilder instance."""
        return HierarchyBuilder(db_session)

    def test_load_complete_hierarchy_empty_database(self, builder, db_session):
        """Test loading hierarchy when database is empty."""
        result = builder.load_complete_hierarchy(db_session)

        # Should return None
        assert result is None

    def test_query_descendants(self, builder, db_session):
        """Test querying descendants from database using recursive SQL."""

        # Create WikidataClass records first
        wikidata_classes_data = [
            {"wikidata_id": "Q1", "name": "Entity 1"},
            {"wikidata_id": "Q2", "name": "Entity 2"},
            {"wikidata_id": "Q3", "name": "Entity 3"},
            {"wikidata_id": "Q4", "name": "Entity 4"},
            {"wikidata_id": "Q5", "name": "Entity 5"},
            {"wikidata_id": "Q6", "name": "Entity 6"},
        ]

        stmt = insert(WikidataClass).values(wikidata_classes_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # Create subclass relations
        subclass_relations = {"Q1": {"Q2", "Q3"}, "Q2": {"Q4"}, "Q3": {"Q5", "Q6"}}
        builder.insert_subclass_relations_batch(subclass_relations, db_session)

        # Query descendants of Q1
        descendants = builder.query_descendants("Q1", db_session)

        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
        assert descendants == expected

    def test_query_descendants_single_node(self, builder, db_session):
        """Test querying descendants for single node from database."""

        # Create WikidataClass record for single node
        wikidata_classes_data = [{"wikidata_id": "Q1", "name": "Entity 1"}]

        stmt = insert(WikidataClass).values(wikidata_classes_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # No subclass relations (empty hierarchy)
        subclass_relations = {}
        builder.insert_subclass_relations_batch(subclass_relations, db_session)

        # Query descendants of Q1
        descendants = builder.query_descendants("Q1", db_session)

        # Should include only the root
        expected = {"Q1"}
        assert descendants == expected

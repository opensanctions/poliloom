"""Tests for HierarchyBuilder."""

import pytest
from sqlalchemy.dialects.postgresql import insert

from poliloom.models import WikidataClass
from poliloom.services.hierarchy_builder import HierarchyBuilder
from .conftest import load_json_fixture


class TestHierarchyBuilder:
    """Test HierarchyBuilder functionality."""

    @pytest.fixture
    def builder(self, db_session):
        """Create a HierarchyBuilder instance."""
        return HierarchyBuilder(db_session)

    def test_get_all_descendants(self, builder):
        """Test building descendant trees using BFS with subclass relations."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        subclass_relations = {
            k: set(v) for k, v in dump_data["subclass_relations_example"].items()
        }

        descendants = builder.get_all_descendants("Q1", subclass_relations)

        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
        assert descendants == expected

    def test_get_all_descendants_single_node(self, builder):
        """Test descendant calculation with single node (no children)."""
        subclass_relations = {}

        descendants = builder.get_all_descendants("Q1", subclass_relations)

        # Should include only the root
        expected = {"Q1"}
        assert descendants == expected

    def test_get_all_descendants_no_children(self, builder):
        """Test descendant calculation with node that has no children."""
        subclass_relations = {"Q1": set(), "Q2": {"Q3"}}

        descendants = builder.get_all_descendants("Q1", subclass_relations)

        # Should include only the root
        expected = {"Q1"}
        assert descendants == expected

    def test_load_complete_hierarchy_empty_database(self, builder, db_session):
        """Test loading hierarchy when database is empty."""
        result = builder.load_complete_hierarchy_from_database(db_session)

        # Should return None
        assert result is None

    def test_query_descendants_from_database(self, builder, db_session):
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
        descendants = builder.query_descendants_from_database("Q1", db_session)

        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
        assert descendants == expected

    def test_query_descendants_single_node_database(self, builder, db_session):
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
        descendants = builder.query_descendants_from_database("Q1", db_session)

        # Should include only the root
        expected = {"Q1"}
        assert descendants == expected

    def test_get_position_and_location_descendants(self, builder):
        """Test extracting position and location descendants from complete hierarchy."""
        # Create test hierarchy that includes both position and location trees
        subclass_relations = {
            "Q294414": {"Q1", "Q2"},  # position root
            "Q2221906": {"Q3", "Q4"},  # location root
            "Q1": {"Q5"},
            "Q3": {"Q6"},
        }

        descendants = builder.get_position_and_location_descendants(subclass_relations)

        # Should have both position and location descendants
        expected_positions = {"Q294414", "Q1", "Q2", "Q5"}
        expected_locations = {"Q2221906", "Q3", "Q4", "Q6"}

        assert descendants["positions"] == expected_positions
        assert descendants["locations"] == expected_locations

    def test_get_position_and_location_descendants_from_database(
        self, builder, db_session
    ):
        """Test extracting position and location descendants from database."""

        # Create WikidataClass records first
        wikidata_classes_data = [
            {"wikidata_id": "Q294414", "name": "Public Office"},
            {"wikidata_id": "Q2221906", "name": "Geographic Location"},
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
        subclass_relations = {
            "Q294414": {"Q1", "Q2"},  # position root
            "Q2221906": {"Q3", "Q4"},  # location root
            "Q1": {"Q5"},
            "Q3": {"Q6"},
        }
        builder.insert_subclass_relations_batch(subclass_relations, db_session)

        descendants = builder.get_position_and_location_descendants_from_database(
            db_session
        )

        # Should have both position and location descendants
        expected_positions = {"Q294414", "Q1", "Q2", "Q5"}
        expected_locations = {"Q2221906", "Q3", "Q4", "Q6"}

        assert descendants["positions"] == expected_positions
        assert descendants["locations"] == expected_locations

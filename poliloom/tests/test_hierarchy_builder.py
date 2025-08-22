"""Tests for HierarchyBuilder."""

import pytest
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

    def test_extract_subclass_relations_from_entity(self, builder):
        """Test extracting P279 relationships from a single entity."""
        # Entity with P279 claims
        entity = {
            "id": "Q123",
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q456"}}}},
                    {"mainsnak": {"datavalue": {"value": {"id": "Q789"}}}},
                ]
            },
        }

        relations = builder.extract_subclass_relations_from_entity(entity)

        # Should map parent IDs to child ID
        expected = {"Q456": {"Q123"}, "Q789": {"Q123"}}
        assert relations == expected

    def test_extract_subclass_relations_from_entity_no_claims(self, builder):
        """Test extracting P279 relationships from entity without claims."""
        entity = {"id": "Q123", "claims": {}}

        relations = builder.extract_subclass_relations_from_entity(entity)

        # Should return empty dict
        assert relations == {}

    def test_extract_subclass_relations_from_entity_malformed(self, builder):
        """Test extracting P279 relationships from entity with malformed claims."""
        entity = {
            "id": "Q123",
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q456"}}}},
                    {
                        "mainsnak": {
                            # Missing datavalue
                        }
                    },
                    {
                        # Missing mainsnak
                    },
                ]
            },
        }

        relations = builder.extract_subclass_relations_from_entity(entity)

        # Should handle malformed claims gracefully
        expected = {"Q456": {"Q123"}}
        assert relations == expected

    def test_extract_entity_name_from_entity(self, builder):
        """Test extracting entity name from labels."""
        # Entity with English and other labels
        entity = {
            "id": "Q123",
            "labels": {
                "en": {"value": "English Name"},
                "de": {"value": "German Name"},
            },
        }

        name = builder.extract_entity_name_from_entity(entity)

        # Should prefer English
        assert name == "English Name"

    def test_extract_entity_name_from_entity_no_english(self, builder):
        """Test extracting entity name without English label."""
        # Entity with only non-English labels
        entity = {
            "id": "Q123",
            "labels": {
                "de": {"value": "German Name"},
                "fr": {"value": "French Name"},
            },
        }

        name = builder.extract_entity_name_from_entity(entity)

        # Should return first available (order not guaranteed in dict)
        assert name in ["German Name", "French Name"]

    def test_extract_entity_name_from_entity_no_labels(self, builder):
        """Test extracting entity name without labels."""
        entity = {"id": "Q123", "labels": {}}

        name = builder.extract_entity_name_from_entity(entity)

        # Should return None
        assert name is None

    def test_save_and_load_complete_hierarchy_database(self, builder, db_session):
        """Test saving and loading complete hierarchy to/from database."""
        # Create test hierarchy
        subclass_relations = {"Q1": {"Q2", "Q3"}, "Q2": {"Q4"}, "Q3": {"Q5", "Q6"}}
        entity_names = {
            "Q1": "Entity 1",
            "Q2": "Entity 2",
            "Q3": "Entity 3",
            "Q4": "Entity 4",
            "Q5": "Entity 5",
            "Q6": "Entity 6",
        }

        # Save to database
        builder.save_complete_hierarchy_to_database(
            subclass_relations, entity_names, db_session
        )

        # Load it back
        loaded_relations = builder.load_complete_hierarchy_from_database(db_session)

        # Should match original
        assert loaded_relations == subclass_relations

    def test_load_complete_hierarchy_empty_database(self, builder, db_session):
        """Test loading hierarchy when database is empty."""
        result = builder.load_complete_hierarchy_from_database(db_session)

        # Should return None
        assert result is None

    def test_query_descendants_from_database(self, builder, db_session):
        """Test querying descendants from database using recursive SQL."""
        # Create test hierarchy
        subclass_relations = {"Q1": {"Q2", "Q3"}, "Q2": {"Q4"}, "Q3": {"Q5", "Q6"}}
        entity_names = {f"Q{i}": f"Entity {i}" for i in range(1, 7)}

        # Save to database
        builder.save_complete_hierarchy_to_database(
            subclass_relations, entity_names, db_session
        )

        # Query descendants of Q1
        descendants = builder.query_descendants_from_database("Q1", db_session)

        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
        assert descendants == expected

    def test_query_descendants_single_node_database(self, builder, db_session):
        """Test querying descendants for single node from database."""
        # Create hierarchy with only one node
        subclass_relations = {}
        entity_names = {"Q1": "Entity 1"}

        # Save to database
        builder.save_complete_hierarchy_to_database(
            subclass_relations, entity_names, db_session
        )

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
        # Create test hierarchy that includes both position and location trees
        subclass_relations = {
            "Q294414": {"Q1", "Q2"},  # position root
            "Q2221906": {"Q3", "Q4"},  # location root
            "Q1": {"Q5"},
            "Q3": {"Q6"},
        }
        entity_names = {f"Q{i}": f"Entity {i}" for i in range(1, 7)}
        entity_names.update(
            {"Q294414": "Public Office", "Q2221906": "Geographic Location"}
        )

        # Save to database
        builder.save_complete_hierarchy_to_database(
            subclass_relations, entity_names, db_session
        )

        descendants = builder.get_position_and_location_descendants_from_database(
            db_session
        )

        # Should have both position and location descendants
        expected_positions = {"Q294414", "Q1", "Q2", "Q5"}
        expected_locations = {"Q2221906", "Q3", "Q4", "Q6"}

        assert descendants["positions"] == expected_positions
        assert descendants["locations"] == expected_locations

    def test_complete_hierarchy_database_integration(self, builder, db_session):
        """Test complete hierarchy save/load database integration."""
        # Create test hierarchy with children only
        subclass_relations = {
            "Q1": {"Q2"},
            "Q2": {"Q3", "Q4"},
            "Q3": {"Q5", "Q6"},
            "Q4": {"Q7"},
        }
        entity_names = {f"Q{i}": f"Entity {i}" for i in range(1, 8)}

        # Save hierarchy to database
        builder.save_complete_hierarchy_to_database(
            subclass_relations, entity_names, db_session
        )

        # Load it back
        loaded_relations = builder.load_complete_hierarchy_from_database(db_session)

        # Should match original
        assert loaded_relations == subclass_relations

        # Should be able to compute descendants using database query
        descendants = builder.query_descendants_from_database("Q1", db_session)
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
        assert descendants == expected

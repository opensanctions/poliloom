"""Tests for HierarchyBuilder."""

import pytest
import tempfile
import os

from poliloom.services.hierarchy_builder import HierarchyBuilder
from .conftest import load_json_fixture


class TestHierarchyBuilder:
    """Test HierarchyBuilder functionality."""

    @pytest.fixture
    def builder(self):
        """Create a HierarchyBuilder instance."""
        return HierarchyBuilder()

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

    def test_save_and_load_complete_hierarchy(self, builder):
        """Test saving and loading complete hierarchy."""
        # Create test hierarchy
        subclass_relations = {"Q1": {"Q2", "Q3"}, "Q2": {"Q4"}, "Q3": {"Q5", "Q6"}}

        # Save to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            builder.save_complete_hierarchy_trees(subclass_relations, temp_dir)

            # Check file was created
            hierarchy_file = os.path.join(temp_dir, "complete_hierarchy.json")
            assert os.path.exists(hierarchy_file)

            # Load it back
            loaded_relations = builder.load_complete_hierarchy(temp_dir)

            # Should match original
            assert loaded_relations == subclass_relations

    def test_load_complete_hierarchy_nonexistent_file(self, builder):
        """Test loading hierarchy when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = builder.load_complete_hierarchy(temp_dir)

            # Should return None
            assert result is None

    def test_load_complete_hierarchy_malformed_json(self, builder):
        """Test loading hierarchy with malformed JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            hierarchy_file = os.path.join(temp_dir, "complete_hierarchy.json")

            # Write malformed JSON
            with open(hierarchy_file, "w") as f:
                f.write("MALFORMED_JSON")

            result = builder.load_complete_hierarchy(temp_dir)

            # Should return None
            assert result is None

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

    def test_complete_hierarchy_integration(self, builder):
        """Test complete hierarchy save/load integration."""
        # Create test hierarchy with children only
        subclass_relations = {
            "Q1": {"Q2"},
            "Q2": {"Q3", "Q4"},
            "Q3": {"Q5", "Q6"},
            "Q4": {"Q7"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            # Save hierarchy
            builder.save_complete_hierarchy_trees(subclass_relations, temp_dir)

            # Load it back
            loaded_relations = builder.load_complete_hierarchy(temp_dir)

            # Should match original
            assert loaded_relations == subclass_relations

            # Should be able to compute descendants
            descendants = builder.get_all_descendants("Q1", loaded_relations)
            expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
            assert descendants == expected

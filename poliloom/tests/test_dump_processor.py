"""Tests for WikidataDumpProcessor orchestration."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock

from poliloom.services.dump_processor import WikidataDumpProcessor
from .conftest import load_json_fixture


class TestWikidataDumpProcessor:
    """Test WikidataDumpProcessor functionality."""

    @pytest.fixture
    def processor(self):
        """Create a WikidataDumpProcessor instance."""
        return WikidataDumpProcessor()

    @pytest.fixture
    def sample_dump_content(self):
        """Create sample dump content for testing."""
        # Load entities from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = dump_data["sample_dump_entities"]

        # Convert to JSON lines format (Wikidata dump format)
        lines = ["[\n"]
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            lines.append(line + "\n")
        lines.append("]\n")

        return "".join(lines)

    def test_build_hierarchy_trees(self, processor, sample_dump_content):
        """Test building hierarchy trees from dump."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Test with 1 worker to avoid multiprocessing complexity in tests
                result = processor.build_hierarchy_trees(
                    temp_file, num_workers=1, output_dir=temp_dir
                )

                # Should return position and location descendants
                assert "positions" in result
                assert "locations" in result
                assert isinstance(result["positions"], set)
                assert isinstance(result["locations"], set)

                # Should create hierarchy file
                hierarchy_file = os.path.join(temp_dir, "complete_hierarchy.json")
                assert os.path.exists(hierarchy_file)

        finally:
            os.unlink(temp_file)

    def test_build_hierarchy_trees_different_worker_counts(
        self, processor, sample_dump_content
    ):
        """Test building hierarchy trees with different worker counts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Test with different worker counts
                for num_workers in [1, 2]:
                    result = processor.build_hierarchy_trees(
                        temp_file, num_workers=num_workers, output_dir=temp_dir
                    )

                    # Should return position and location descendants
                    assert "positions" in result
                    assert "locations" in result

        finally:
            os.unlink(temp_file)

    def test_process_chunk(self, processor):
        """Test processing a chunk of the dump file."""
        # Create test content for chunk processing
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {},
                "claims": {
                    "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}]
                },
            },
            {"id": "Q2", "type": "item", "labels": {}, "claims": {}},
        ]

        content = "[\n"
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            content += line + "\n"
        content += "]\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            # Process the entire file as one chunk
            file_size = os.path.getsize(temp_file)
            subclass_relations, entity_count = processor._process_chunk(
                temp_file, 0, file_size, worker_id=0
            )

            # Should extract the P279 relationship
            assert "Q2" in subclass_relations
            assert "Q1" in subclass_relations["Q2"]
            assert entity_count == 2

        finally:
            os.unlink(temp_file)

    def test_build_hierarchy_trees_with_complex_relationships(self, processor):
        """Test building hierarchy trees with complex P279 relationships."""
        # Create dump content with complex hierarchy
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {},
                "claims": {
                    "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}]
                },
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {},
                "claims": {
                    "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q3"}}}}]
                },
            },
            {"id": "Q3", "type": "item", "labels": {}, "claims": {}},
            {
                "id": "Q4",
                "type": "item",
                "labels": {},
                "claims": {
                    "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}]
                },
            },
        ]

        content = "[\n"
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            content += line + "\n"
        content += "]\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = processor.build_hierarchy_trees(
                    temp_file, num_workers=1, output_dir=temp_dir
                )

                # Should return position and location descendants
                assert "positions" in result
                assert "locations" in result

                # Load the saved hierarchy to verify relationships
                loaded_relations = processor.hierarchy_builder.load_complete_hierarchy(
                    temp_dir
                )

                # Should have captured the relationships
                assert "Q2" in loaded_relations
                assert "Q3" in loaded_relations
                assert "Q1" in loaded_relations["Q2"]
                assert "Q4" in loaded_relations["Q2"]
                assert "Q2" in loaded_relations["Q3"]

        finally:
            os.unlink(temp_file)

    def test_build_hierarchy_trees_with_malformed_claims(self, processor):
        """Test building hierarchy trees with malformed P279 claims."""
        # Create dump content with malformed claims
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {},
                "claims": {
                    "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}]
                },
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {},
                "claims": {"P279": [{"mainsnak": {}}]},
            },  # Malformed
            {
                "id": "Q3",
                "type": "item",
                "labels": {},
                "claims": {"P279": [{}]},
            },  # Malformed
        ]

        content = "[\n"
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            content += line + "\n"
        content += "]\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Should not raise exception despite malformed claims
                result = processor.build_hierarchy_trees(
                    temp_file, num_workers=1, output_dir=temp_dir
                )

                # Should return position and location descendants
                assert "positions" in result
                assert "locations" in result

                # Load the saved hierarchy to verify only valid relationships were captured
                loaded_relations = processor.hierarchy_builder.load_complete_hierarchy(
                    temp_dir
                )

                # Should only have the valid relationship
                assert "Q2" in loaded_relations
                assert "Q1" in loaded_relations["Q2"]
                # Should not have invalid relationships
                assert len(loaded_relations) == 1

        finally:
            os.unlink(temp_file)

    def test_extract_entities_from_dump_integration(self, processor):
        """Test complete entity extraction workflow."""
        # Create test entities that should be extracted
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"value": "Test Position"}},
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q294414"}}}}]
                },
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {"en": {"value": "Test Location"}},
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q2221906"}}}}]
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"value": "Test Country"}},
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q6256"}}}}]
                },
            },
        ]

        content = "[\n"
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            content += line + "\n"
        content += "]\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create hierarchy file first
                hierarchy_data = {
                    "subclass_of": {
                        "Q294414": ["Q1"],  # position
                        "Q2221906": ["Q2"],  # location
                    }
                }

                hierarchy_file = os.path.join(temp_dir, "complete_hierarchy.json")
                with open(hierarchy_file, "w") as f:
                    json.dump(hierarchy_data, f)

                # Mock database operations
                with patch(
                    "poliloom.services.worker_manager.get_worker_session"
                ) as mock_get_session:
                    mock_session = MagicMock()
                    mock_get_session.return_value = mock_session

                    # Mock query to return no existing entities
                    mock_query = MagicMock()
                    mock_session.query.return_value = mock_query
                    mock_query.filter.return_value = mock_query
                    mock_query.all.return_value = []

                    # Mock execute for countries
                    mock_result = MagicMock()
                    mock_result.rowcount = 1
                    mock_session.execute.return_value = mock_result

                    # Test extraction
                    result = processor.extract_entities_from_dump(
                        temp_file, batch_size=10, num_workers=1, hierarchy_dir=temp_dir
                    )

                    # Should have extracted all entity types
                    assert result["positions"] == 1
                    assert result["locations"] == 1
                    assert result["countries"] == 1

        finally:
            os.unlink(temp_file)

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
                    assert (
                        result["politicians"] == 0
                    )  # No politicians in this test data

        finally:
            os.unlink(temp_file)

    def test_extract_politicians_from_dump_integration(self, processor):
        """Test complete politician extraction workflow."""
        # Create test entities including politicians
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
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q6256"}}}}],
                    "P297": [{"mainsnak": {"datavalue": {"value": "TC"}}}],
                },
            },
            {
                "id": "Q4",
                "type": "item",
                "labels": {"en": {"value": "John Doe"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q82955"}}}}
                    ],  # politician
                    "P569": [
                        {
                            "mainsnak": {
                                "datavalue": {
                                    "type": "time",
                                    "value": {
                                        "time": "+1970-01-01T00:00:00Z",
                                        "precision": 11,
                                    },
                                }
                            }
                        }
                    ],  # birth date
                    "P27": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q3"}}}}
                    ],  # citizenship
                    "P39": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q1"}}}}
                    ],  # position held
                    "P19": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}
                    ],  # birthplace
                },
                "sitelinks": {
                    "enwiki": {"title": "John Doe"},
                    "frwiki": {"title": "John Doe"},
                },
            },
            {
                "id": "Q5",
                "type": "item",
                "labels": {"en": {"value": "Jane Smith"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P39": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q1"}}}}
                    ],  # position held (makes them a politician)
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

                    # Mock queries for different entity types
                    mock_query = MagicMock()
                    mock_session.query.return_value = mock_query
                    mock_query.filter.return_value = mock_query
                    mock_query.filter_by.return_value = mock_query
                    mock_query.all.return_value = []  # No existing entities

                    # Mock existing entities for politician relationships
                    mock_position = MagicMock()
                    mock_position.id = 1
                    mock_country = MagicMock()
                    mock_country.id = 1
                    mock_location = MagicMock()
                    mock_location.id = 1

                    # Set up query returns for politician relationships
                    def mock_first_side_effect():
                        return mock_position

                    mock_query.first.side_effect = [
                        mock_position,  # Position for John Doe
                        mock_country,  # Country for John Doe
                        mock_location,  # Location for John Doe
                        mock_position,  # Position for Jane Smith
                    ]

                    # Mock execute for countries
                    mock_result = MagicMock()
                    mock_result.rowcount = 1
                    mock_session.execute.return_value = mock_result

                    # Test politician extraction using chunk processing
                    # (multiprocessing with mocked database sessions has issues)
                    with patch(
                        "poliloom.services.worker_manager.get_hierarchy_sets"
                    ) as mock_get_hierarchy:
                        mock_get_hierarchy.return_value = (
                            set(),
                            set(),
                        )  # Empty sets for politician extraction

                        file_size = os.path.getsize(temp_file)
                        counts, entity_count = processor._process_politicians_chunk(
                            temp_file,
                            0,
                            file_size,
                            worker_id=0,
                            batch_size=10,
                        )

                        # Should have extracted only politicians (since supporting entities are imported separately)
                        assert counts["positions"] == 0
                        assert counts["locations"] == 0
                        assert counts["countries"] == 0
                        assert counts["politicians"] == 2  # John Doe and Jane Smith
                        assert entity_count == 5  # Total entities processed

        finally:
            os.unlink(temp_file)

    def test_process_entity_chunk_with_politicians(self, processor):
        """Test processing a chunk that includes politicians."""
        # Create test content with politicians
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"value": "John Doe"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q82955"}}}}
                    ],  # politician
                },
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {"en": {"value": "Jane Smith"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P39": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q30185"}}}}
                    ],  # position held
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"value": "Not a politician"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q999"}}}}
                    ],  # not politician
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
            # Mock database operations
            with patch(
                "poliloom.services.worker_manager.get_worker_session"
            ) as mock_get_session:
                mock_session = MagicMock()
                mock_get_session.return_value = mock_session

                # Mock queries to return no existing entities
                mock_query = MagicMock()
                mock_session.query.return_value = mock_query
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = []

                # Mock hierarchy sets
                with patch(
                    "poliloom.services.worker_manager.get_hierarchy_sets"
                ) as mock_get_hierarchy:
                    mock_get_hierarchy.return_value = (set(), set())  # Empty sets

                    # Process the entire file as one chunk
                    file_size = os.path.getsize(temp_file)
                    counts, entity_count = processor._process_politicians_chunk(
                        temp_file,
                        0,
                        file_size,
                        worker_id=0,
                        batch_size=10,
                    )

                    # Should have identified 2 politicians
                    assert counts["politicians"] == 2
                    assert entity_count == 3  # Total entities processed

        finally:
            os.unlink(temp_file)

    def test_politician_extraction_with_malformed_data(self, processor):
        """Test politician extraction with malformed data."""
        # Create test content with malformed politician data
        entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"value": "John Doe"}},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q82955"}}}}
                    ],  # politician
                },
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {},  # No name - should be skipped
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ],  # human
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q82955"}}}}
                    ],  # politician
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"value": "Jane Smith"}},
                "claims": {
                    "P31": [{"mainsnak": {}}],  # Malformed claim
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q82955"}}}}
                    ],  # politician
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
            # Mock database operations
            with patch(
                "poliloom.services.worker_manager.get_worker_session"
            ) as mock_get_session:
                mock_session = MagicMock()
                mock_get_session.return_value = mock_session

                # Mock queries to return no existing entities
                mock_query = MagicMock()
                mock_session.query.return_value = mock_query
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = []

                # Mock hierarchy sets
                with patch(
                    "poliloom.services.worker_manager.get_hierarchy_sets"
                ) as mock_get_hierarchy:
                    mock_get_hierarchy.return_value = (set(), set())  # Empty sets

                    # Process the entire file as one chunk
                    file_size = os.path.getsize(temp_file)
                    counts, entity_count = processor._process_politicians_chunk(
                        temp_file,
                        0,
                        file_size,
                        worker_id=0,
                        batch_size=10,
                    )

                    # Should have extracted only 1 politician (Q1)
                    # Q2 has no name, Q3 has malformed claims
                    assert counts["politicians"] == 1
                    assert entity_count == 3  # Total entities processed

        finally:
            os.unlink(temp_file)

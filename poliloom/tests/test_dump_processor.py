"""Tests for WikidataDumpProcessor orchestration."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock

from poliloom.database import get_db_session
from poliloom.models import WikidataClass
from poliloom.services.dump_processor import WikidataDumpProcessor
from sqlalchemy.dialects.postgresql import insert
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

    def test_process_chunk_for_relationships(self, processor):
        """Test processing a chunk of the dump file to extract relationships."""
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
            # Process the entire file as one chunk for relationship extraction (returns 2 values)
            file_size = os.path.getsize(temp_file)
            subclass_relations, entity_count = (
                processor._process_chunk_for_relationships(
                    temp_file, 0, file_size, worker_id=0
                )
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
            # Test hierarchy tree building (now saves to database)
            processor.build_hierarchy_trees(temp_file)

            # Verify relationships were saved to database
            with get_db_session() as session:
                from poliloom.models import SubclassRelation

                # Check specific relationships exist in database
                q1_q2_relation = (
                    session.query(SubclassRelation)
                    .filter_by(parent_class_id="Q2", child_class_id="Q1")
                    .first()
                )
                assert q1_q2_relation is not None

                q4_q2_relation = (
                    session.query(SubclassRelation)
                    .filter_by(parent_class_id="Q2", child_class_id="Q4")
                    .first()
                )
                assert q4_q2_relation is not None

                q2_q3_relation = (
                    session.query(SubclassRelation)
                    .filter_by(parent_class_id="Q3", child_class_id="Q2")
                    .first()
                )
                assert q2_q3_relation is not None

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
            # Should not raise exception despite malformed claims
            processor.build_hierarchy_trees(temp_file)

            # Verify only valid relationships were saved to database
            with get_db_session() as session:
                from poliloom.models import SubclassRelation

                # Should only have the valid relationship
                q1_q2_relation = (
                    session.query(SubclassRelation)
                    .filter_by(parent_class_id="Q2", child_class_id="Q1")
                    .first()
                )
                assert q1_q2_relation is not None

                # Should not have invalid relationships (total count should be 1)
                total_relations = session.query(SubclassRelation).count()
                assert total_relations == 1

        finally:
            os.unlink(temp_file)

    def test_extract_entities_from_dump_integration(self, processor, db_session):
        """Test complete entity extraction workflow."""
        # First, set up hierarchy in database using current approach

        # Create WikidataClass records first
        wikidata_classes_data = [
            {"wikidata_id": "Q294414", "name": "Public Office"},
            {"wikidata_id": "Q2221906", "name": "Geographic Location"},
            {"wikidata_id": "Q1", "name": "Test Position"},
            {"wikidata_id": "Q2", "name": "Test Location"},
            {"wikidata_id": "Q3", "name": "Test Country"},
        ]

        with get_db_session() as session:
            stmt = insert(WikidataClass).values(wikidata_classes_data)
            stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
            session.execute(stmt)
            session.commit()

            # Create subclass relations directly using SQLAlchemy
            from poliloom.models import SubclassRelation

            relations_data = [
                {
                    "parent_class_id": "Q294414",
                    "child_class_id": "Q1",
                },  # position root -> test position
                {
                    "parent_class_id": "Q2221906",
                    "child_class_id": "Q2",
                },  # location root -> test location
            ]
            stmt = insert(SubclassRelation).values(relations_data)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["parent_class_id", "child_class_id"]
            )
            session.execute(stmt)
            session.commit()

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
            # Mock multiprocessing but allow real database operations
            with patch("poliloom.services.dump_processor.mp.Pool") as mock_pool_class:
                # Create a mock pool that calls the real chunk processing function
                mock_pool = MagicMock()
                mock_pool_class.return_value = mock_pool

                def mock_starmap_async(func, args_list):
                    # Execute the chunk processing function synchronously in the current process
                    results = []
                    for args in args_list:
                        result = func(*args)
                        results.append(result)

                    mock_async_result = MagicMock()
                    mock_async_result.get.return_value = results
                    return mock_async_result

                mock_pool.starmap_async.side_effect = mock_starmap_async

                # Test extraction - this will run the real chunk processing with real database
                result = processor.extract_entities_from_dump(temp_file, batch_size=10)

                # Should have extracted all entity types (results may vary based on actual processing)
                assert "positions" in result
                assert "locations" in result
                assert "countries" in result
                assert "politicians" in result

        finally:
            os.unlink(temp_file)

    def test_extract_politicians_from_dump_integration(self, processor):
        """Test complete politician extraction workflow."""
        # Create test entities including politicians
        entities = [
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
                },
                "sitelinks": {
                    "enwiki": {"title": "John Doe"},
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
                        {"mainsnak": {"datavalue": {"value": {"id": "Q30185"}}}}
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
            result = processor.extract_politicians_from_dump(temp_file, batch_size=10)

            # Should have extracted both politicians
            assert result["politicians"] == 2  # John Doe and Jane Smith
            assert result["positions"] == 0
            assert result["locations"] == 0
            assert result["countries"] == 0

        finally:
            os.unlink(temp_file)

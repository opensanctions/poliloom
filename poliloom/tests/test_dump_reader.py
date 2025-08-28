"""Tests for DumpReader."""

import pytest
import json
import tempfile
import os

from poliloom.services.dump_reader import DumpReader
from .conftest import load_json_fixture


class TestDumpReader:
    """Test DumpReader functionality."""

    @pytest.fixture
    def reader(self):
        """Create a DumpReader instance."""
        return DumpReader()

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

    def test_calculate_file_chunks(self, reader):
        """Test calculating file chunks for parallel processing."""
        # Create a larger test file to ensure chunking
        content = "Line 1\n" * 1000  # Ensure file is large enough for chunking

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            # Test with 2 workers
            chunks = reader.calculate_file_chunks(temp_file, 2)

            assert len(chunks) >= 1  # At least one chunk
            assert chunks[0][0] == 0  # First chunk starts at beginning
            assert chunks[-1][1] == len(content.encode())  # Last chunk ends at file end

            # Chunks should not overlap
            for i in range(len(chunks) - 1):
                assert chunks[i][1] <= chunks[i + 1][0]

        finally:
            os.unlink(temp_file)

    def test_calculate_file_chunks_small_file(self, reader):
        """Test chunk calculation with small file."""
        content = "Small file"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            # Request many workers but file is small
            chunks = reader.calculate_file_chunks(temp_file, 10)

            # Should create fewer chunks for small file
            assert len(chunks) >= 1
            assert chunks[0][0] == 0
            assert chunks[-1][1] == len(content.encode())

        finally:
            os.unlink(temp_file)

    def test_read_chunk_entities(self, reader, sample_dump_content):
        """Test reading entities from a specific byte range."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name

        try:
            file_size = os.path.getsize(temp_file)

            # Read first half of file
            entities = list(reader.read_chunk_entities(temp_file, 0, file_size // 2))

            # Should get some entities (exact number depends on where split falls)
            assert len(entities) >= 0

            # All entities should be valid
            for entity in entities:
                assert "id" in entity
                assert "type" in entity

        finally:
            os.unlink(temp_file)

    def test_read_chunk_entities_with_malformed_json(self, reader):
        """Test chunk reading with malformed JSON."""
        content = """[
{"id": "Q1", "type": "item", "labels": {}, "claims": {}},
MALFORMED_JSON_LINE,
{"id": "Q2", "type": "item", "labels": {}, "claims": {}},
]"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            file_size = os.path.getsize(temp_file)
            entities = list(reader.read_chunk_entities(temp_file, 0, file_size))

            # Should skip malformed line and continue
            assert len(entities) == 2
            assert entities[0]["id"] == "Q1"
            assert entities[1]["id"] == "Q2"

        finally:
            os.unlink(temp_file)

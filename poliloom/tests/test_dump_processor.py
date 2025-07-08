"""Tests for WikidataDumpProcessor."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

from poliloom.services.dump_processor import WikidataDumpProcessor


class TestWikidataDumpProcessor:
    """Test WikidataDumpProcessor functionality."""

    @pytest.fixture
    def processor(self):
        """Create a WikidataDumpProcessor instance."""
        return WikidataDumpProcessor()

    @pytest.fixture
    def sample_dump_content(self):
        """Create sample dump content for testing."""
        entities = [
            {
                "id": "Q294414",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "public office"}},
                "claims": {}
            },
            {
                "id": "Q2221906",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "geographic location"}},
                "claims": {}
            },
            {
                "id": "Q1001",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Member of Parliament"}},
                "claims": {
                    "P279": [{
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {"id": "Q294414"}
                            }
                        }
                    }]
                }
            },
            {
                "id": "Q1002",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Mayor"}},
                "claims": {
                    "P279": [{
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {"id": "Q294414"}
                            }
                        }
                    }]
                }
            },
            {
                "id": "Q1003",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "President"}},
                "claims": {
                    "P279": [{
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {"id": "Q1001"}
                            }
                        }
                    }]
                }
            },
            {
                "id": "Q2001",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "City"}},
                "claims": {
                    "P279": [{
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {"id": "Q2221906"}
                            }
                        }
                    }]
                }
            },
            {
                "id": "Q2002",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Capital"}},
                "claims": {
                    "P279": [{
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {
                                "type": "wikibase-entityid",
                                "value": {"id": "Q2001"}
                            }
                        }
                    }]
                }
            },
            {
                "id": "Q5",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Human"}},
                "claims": {}
            }
        ]
        
        # Convert to JSON lines format (Wikidata dump format)
        lines = ["[\n"]
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            lines.append(line + "\n")
        lines.append("]\n")
        
        return "".join(lines)

    def test_stream_dump_entities(self, processor, sample_dump_content):
        """Test streaming entities from dump file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name
        
        try:
            entities = list(processor._stream_dump_entities(temp_file))
            
            assert len(entities) == 8
            assert entities[0]["id"] == "Q294414"
            assert entities[1]["id"] == "Q2221906"
            assert entities[7]["id"] == "Q5"
            
            # Check that all entities have required fields
            for entity in entities:
                assert "id" in entity
                assert "type" in entity
                assert "labels" in entity
                assert "claims" in entity
        
        finally:
            os.unlink(temp_file)

    def test_stream_dump_entities_with_malformed_json(self, processor):
        """Test handling of malformed JSON lines."""
        content = """[
{"id": "Q1", "type": "item", "labels": {}, "claims": {}},
MALFORMED_JSON_LINE,
{"id": "Q2", "type": "item", "labels": {}, "claims": {}},
]"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            entities = list(processor._stream_dump_entities(temp_file))
            
            # Should skip malformed line and continue
            assert len(entities) == 2
            assert entities[0]["id"] == "Q1"
            assert entities[1]["id"] == "Q2"
        
        finally:
            os.unlink(temp_file)

    def test_get_all_descendants(self, processor):
        """Test building descendant trees using BFS."""
        subclass_relations = {
            "Q1": {"Q2", "Q3"},
            "Q2": {"Q4", "Q5"},
            "Q3": {"Q6"},
            "Q4": {"Q7"},
            "Q5": set(),
            "Q6": set(),
            "Q7": set()
        }
        
        descendants = processor._get_all_descendants("Q1", subclass_relations)
        
        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
        assert descendants == expected

    def test_get_all_descendants_single_node(self, processor):
        """Test descendant tree with single node."""
        subclass_relations = {
            "Q1": set()
        }
        
        descendants = processor._get_all_descendants("Q1", subclass_relations)
        
        assert descendants == {"Q1"}

    def test_get_all_descendants_no_children(self, processor):
        """Test descendant tree when node has no children."""
        subclass_relations = {}
        
        descendants = processor._get_all_descendants("Q1", subclass_relations)
        
        assert descendants == {"Q1"}

    def test_build_hierarchy_trees(self, processor, sample_dump_content):
        """Test building complete hierarchy trees from dump using parallel processing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name
        
        try:
            trees = processor.build_hierarchy_trees(temp_file, num_workers=2)
            
            # Check position tree
            assert "positions" in trees
            positions = trees["positions"]
            assert "Q294414" in positions  # Root
            assert "Q1001" in positions     # Member of Parliament
            assert "Q1002" in positions     # Mayor
            assert "Q1003" in positions     # President (descendant of Q1001)
            assert len(positions) == 4
            
            # Check location tree
            assert "locations" in trees
            locations = trees["locations"]
            assert "Q2221906" in locations  # Root
            assert "Q2001" in locations     # City
            assert "Q2002" in locations     # Capital (descendant of Q2001)
            assert len(locations) == 3
            
            # Ensure no overlap between trees
            assert len(positions & locations) == 0
        
        finally:
            os.unlink(temp_file)
    
    def test_build_hierarchy_trees_different_worker_counts(self, processor, sample_dump_content):
        """Test that different worker counts produce identical results."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name
        
        try:
            # Run with 1 worker
            trees_1_worker = processor.build_hierarchy_trees(temp_file, num_workers=1)
            
            # Run with 2 workers
            trees_2_workers = processor.build_hierarchy_trees(temp_file, num_workers=2)
            
            # Results should be identical
            assert trees_1_worker["positions"] == trees_2_workers["positions"]
            assert trees_1_worker["locations"] == trees_2_workers["locations"]
        
        finally:
            os.unlink(temp_file)
    
    def test_calculate_file_chunks(self, processor):
        """Test file chunking logic."""
        # Create a test file with multiple lines
        test_content = "line1\nline2\nline3\nline4\nline5\nline6\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Test with 2 workers
            chunks = processor._calculate_file_chunks(temp_file, 2)
            
            assert len(chunks) <= 2  # Should create at most 2 chunks
            
            # Verify chunks don't overlap and cover the whole file
            file_size = os.path.getsize(temp_file)
            assert chunks[0][0] == 0  # First chunk starts at beginning
            assert chunks[-1][1] == file_size  # Last chunk ends at file end
            
            # Verify chunks are non-empty
            for start, end in chunks:
                assert start < end
        
        finally:
            os.unlink(temp_file)
    
    def test_process_chunk(self, processor):
        """Test processing a specific chunk of the file."""
        # Create test JSON content
        entities = [
            {"id": "Q1", "type": "item", "claims": {}},
            {"id": "Q2", "type": "item", "claims": {
                "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q1"}}}}]
            }},
            {"id": "Q3", "type": "item", "claims": {}}
        ]
        
        # Convert to JSON lines format
        lines = ["[\n"]
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            lines.append(line + "\n")
        lines.append("]\n")
        content = "".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            file_size = os.path.getsize(temp_file)
            
            # Process the entire file as one chunk
            relations, count = processor._process_chunk(temp_file, 0, file_size, 0)
            
            assert count == 3  # Should find 3 entities
            assert "Q1" in relations  # Q2 is subclass of Q1
            assert "Q2" in relations["Q1"]
        
        finally:
            os.unlink(temp_file)

    def test_save_and_load_complete_subclass_tree(self, processor):
        """Test saving and loading the complete subclass tree."""
        test_relations = {
            "Q1": {"Q2", "Q3"},
            "Q2": {"Q4"},
            "Q5": {"Q6", "Q7", "Q8"}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save complete tree
            processor.save_complete_subclass_tree(test_relations, temp_dir)
            
            # Check file was created
            tree_file = os.path.join(temp_dir, "complete_subclass_tree.json")
            assert os.path.exists(tree_file)
            
            # Load tree back
            loaded_relations = processor.load_complete_subclass_tree(temp_dir)
            
            assert loaded_relations is not None
            assert loaded_relations["Q1"] == {"Q2", "Q3"}
            assert loaded_relations["Q2"] == {"Q4"}
            assert loaded_relations["Q5"] == {"Q6", "Q7", "Q8"}

    def test_get_descendants_from_complete_tree(self, processor):
        """Test extracting descendants from the complete tree."""
        test_relations = {
            "Q1": {"Q2", "Q3"},
            "Q2": {"Q4"},
            "Q3": {"Q5"}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save complete tree
            processor.save_complete_subclass_tree(test_relations, temp_dir)
            
            # Extract descendants of Q1
            descendants = processor.get_descendants_from_complete_tree("Q1", temp_dir)
            
            assert descendants is not None
            expected = {"Q1", "Q2", "Q3", "Q4", "Q5"}  # Q1 + all descendants
            assert descendants == expected

    def test_complete_tree_integration(self, processor, sample_dump_content):
        """Test that complete tree is saved during build_hierarchy_trees."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(sample_dump_content)
            temp_file = f.name
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Change working directory for this test
                original_cwd = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # Build trees (should save complete tree)
                    trees = processor.build_hierarchy_trees(temp_file, num_workers=1)
                    
                    # Check that complete tree file was created
                    assert os.path.exists("complete_subclass_tree.json")
                    
                    # Load and verify complete tree
                    complete_tree = processor.load_complete_subclass_tree(".")
                    assert complete_tree is not None
                    
                    # Should contain the relationships from our sample data
                    assert "Q294414" in complete_tree  # public office has subclasses
                    assert "Q2221906" in complete_tree  # geographic location has subclasses
                    
                finally:
                    os.chdir(original_cwd)
        
        finally:
            os.unlink(temp_file)


    def test_build_hierarchy_trees_with_complex_relationships(self, processor):
        """Test building trees with complex P279 relationships."""
        entities = [
            {
                "id": "Q294414",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "public office"}},
                "claims": {}
            },
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Position A"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "datatype": "wikibase-item",
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q294414"}
                                }
                            }
                        },
                        {
                            "mainsnak": {
                                "datatype": "wikibase-item",
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q999"}  # Non-existent parent
                                }
                            }
                        }
                    ]
                }
            }
        ]
        
        # Convert to JSON lines format
        lines = ["[\n"]
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            lines.append(line + "\n")
        lines.append("]\n")
        content = "".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            trees = processor.build_hierarchy_trees(temp_file)
            
            # Should still include Q1 as descendant of Q294414
            assert "Q1" in trees["positions"]
        
        finally:
            os.unlink(temp_file)

    def test_build_hierarchy_trees_with_malformed_claims(self, processor):
        """Test handling of malformed P279 claims."""
        entities = [
            {
                "id": "Q294414",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "public office"}},
                "claims": {}
            },
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Position A"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                # Missing datavalue
                                "datatype": "wikibase-item"
                            }
                        }
                    ]
                }
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Position B"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "datatype": "wikibase-item",
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q294414"}
                                }
                            }
                        }
                    ]
                }
            }
        ]
        
        # Convert to JSON lines format
        lines = ["[\n"]
        for i, entity in enumerate(entities):
            line = json.dumps(entity)
            if i < len(entities) - 1:
                line += ","
            lines.append(line + "\n")
        lines.append("]\n")
        content = "".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            trees = processor.build_hierarchy_trees(temp_file)
            
            # Should handle malformed claim gracefully
            assert "Q1" not in trees["positions"]  # Malformed claim
            assert "Q2" in trees["positions"]       # Valid claim
        
        finally:
            os.unlink(temp_file)
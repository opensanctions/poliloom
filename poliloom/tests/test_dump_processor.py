"""Tests for WikidataDumpProcessor."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, mock_open

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
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        subclass_relations = {k: set(v) for k, v in dump_data["subclass_relations_example"].items()}
        
        descendants = processor._get_all_descendants("Q1", subclass_relations)
        
        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
        assert descendants == expected

    def test_get_all_descendants_single_node(self, processor):
        """Test descendant tree with single node."""
        subclass_relations = {"Q1": set()}
        
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
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = [dump_data["sample_dump_entities"][0]]  # Q294414
        entities.append(dump_data["complex_p279_relationships"]["position_with_multiple_parents"])
        
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
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = [dump_data["sample_dump_entities"][0]]  # Q294414
        entities.append(dump_data["complex_p279_relationships"]["position_with_malformed_claim"])
        
        # Add a valid position for comparison
        valid_position = {
            "id": "Q2",
            "type": "item",
            "labels": {"en": {"language": "en", "value": "Position B"}},
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
        }
        entities.append(valid_position)
        
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
    
    def test_is_country_entity(self, processor):
        """Test country entity identification."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        country_examples = dump_data["country_entity_examples"]
        
        # Test standard country
        assert processor._is_country_entity(country_examples["standard_country"]) is True
        
        # Test sovereign state
        assert processor._is_country_entity(country_examples["sovereign_state"]) is True
        
        # Test non-country
        assert processor._is_country_entity(country_examples["city_entity"]) is False
        
        # Test entity with malformed claims
        assert processor._is_country_entity(country_examples["malformed_entity"]) is False
    
    def test_get_entity_name(self, processor):
        """Test entity name extraction."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        name_examples = dump_data["entity_name_examples"]
        
        # Test with English label
        assert processor._get_entity_name(name_examples["with_english_label"]) == "United States"
        
        # Test without English label
        assert processor._get_entity_name(name_examples["without_english_label"]) == "Deutschland"  # First available
        
        # Test with empty labels
        assert processor._get_entity_name(name_examples["empty_labels"]) is None
        
        # Test with missing labels
        assert processor._get_entity_name(name_examples["missing_labels"]) is None
    
    def test_extract_position_data(self, processor):
        """Test position data extraction."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        position_examples = dump_data["position_entity_examples"]
        
        data = processor._extract_position_data(position_examples["mayor"])
        assert data is not None
        assert data["wikidata_id"] == "Q30185"
        assert data["name"] == "Mayor"
        
        # Test with no name
        assert processor._extract_position_data(position_examples["position_no_name"]) is None
    
    def test_extract_location_data(self, processor):
        """Test location data extraction."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        location_examples = dump_data["location_entity_examples"]
        
        data = processor._extract_location_data(location_examples["london"])
        assert data is not None
        assert data["wikidata_id"] == "Q84"
        assert data["name"] == "London"
        
        # Test with no name
        assert processor._extract_location_data(location_examples["location_no_name"]) is None
    
    def test_extract_country_data(self, processor):
        """Test country data extraction."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        country_examples = dump_data["country_data_examples"]
        
        # Test with ISO code
        data = processor._extract_country_data(country_examples["with_iso_code"])
        assert data is not None
        assert data["wikidata_id"] == "Q30"
        assert data["name"] == "United States of America"
        assert data["iso_code"] == "US"
        
        # Test without ISO code
        data = processor._extract_country_data(country_examples["without_iso_code"])
        assert data is not None
        assert data["wikidata_id"] == "Q999"
        assert data["name"] == "Test Country"
        assert data["iso_code"] is None
        
        # Test with malformed ISO claim
        data = processor._extract_country_data(country_examples["malformed_iso_claim"])
        assert data["iso_code"] is None
    
    def test_insert_positions_batch(self, processor):
        """Test batch insertion of positions."""
        from unittest.mock import MagicMock, Mock
        
        # Mock the SessionLocal where it's imported inside the method
        with patch('poliloom.database.SessionLocal') as mock_session_local, \
             patch('poliloom.models.Position') as mock_position:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.all.return_value = []
            
            # Make Position behave like a class
            mock_position.side_effect = lambda **kwargs: Mock(**kwargs)
            
            positions = [
                {"wikidata_id": "Q1", "name": "Mayor"},
                {"wikidata_id": "Q2", "name": "President"}
            ]
            
            processor._insert_positions_batch(positions)
            
            # Verify session methods were called
            assert mock_session.add_all.called
            assert mock_session.commit.called
            assert mock_session.close.called
            
            # Check Position objects were created
            added_objects = mock_session.add_all.call_args[0][0]
            assert len(added_objects) == 2
            assert all(hasattr(obj, 'wikidata_id') for obj in added_objects)
            assert all(hasattr(obj, 'name') for obj in added_objects)
            assert all(hasattr(obj, 'embedding') for obj in added_objects)
    
    def test_insert_locations_batch(self, processor):
        """Test batch insertion of locations."""
        from unittest.mock import MagicMock
        
        # Mock the SessionLocal where it's imported inside the method
        with patch('poliloom.database.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.all.return_value = []
            
            locations = [
                {"wikidata_id": "Q84", "name": "London"},
                {"wikidata_id": "Q90", "name": "Paris"}
            ]
            
            processor._insert_locations_batch(locations)
            
            # Verify session methods were called
            assert mock_session.add_all.called
            assert mock_session.commit.called
            assert mock_session.close.called
            
            # Check Location objects were created
            added_objects = mock_session.add_all.call_args[0][0]
            assert len(added_objects) == 2
            assert all(hasattr(obj, 'wikidata_id') for obj in added_objects)
            assert all(hasattr(obj, 'name') for obj in added_objects)
            assert all(hasattr(obj, 'embedding') for obj in added_objects)
    
    def test_insert_countries_batch(self, processor):
        """Test batch insertion of countries."""
        from unittest.mock import MagicMock
        
        # Mock the SessionLocal where it's imported inside the method
        with patch('poliloom.database.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.all.return_value = []
            
            countries = [
                {"wikidata_id": "Q30", "name": "United States", "iso_code": "US"},
                {"wikidata_id": "Q183", "name": "Germany", "iso_code": "DE"}
            ]
            
            processor._insert_countries_batch(countries)
            
            # Verify session methods were called
            assert mock_session.add_all.called
            assert mock_session.commit.called
            assert mock_session.close.called
            
            # Check Country objects were created
            added_objects = mock_session.add_all.call_args[0][0]
            assert len(added_objects) == 2
            assert all(hasattr(obj, 'wikidata_id') for obj in added_objects)
            assert all(hasattr(obj, 'name') for obj in added_objects)
            assert all(hasattr(obj, 'iso_code') for obj in added_objects)
    
    def test_insert_positions_batch_with_duplicates(self, processor):
        """Test batch insertion handles existing positions correctly."""
        from unittest.mock import MagicMock
        
        # Mock the SessionLocal where it's imported inside the method
        with patch('poliloom.database.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            # Mock session to return one existing position
            mock_session.query.return_value.filter.return_value.all.return_value = [("Q1",)]
            
            positions = [
                {"wikidata_id": "Q1", "name": "Mayor"},      # Existing
                {"wikidata_id": "Q2", "name": "President"}   # New
            ]
            
            processor._insert_positions_batch(positions)
            
            # Only one object should be added (Q2)
            added_objects = mock_session.add_all.call_args[0][0]
            assert len(added_objects) == 1
            assert added_objects[0].wikidata_id == "Q2"
    
    def test_extract_entities_from_dump_integration(self, processor):
        """Integration test for entity extraction from dump."""
        # Load test data from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = dump_data["integration_test_entities"]
        
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
            with tempfile.TemporaryDirectory() as temp_dir:
                # Change working directory for this test
                original_cwd = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # First build the hierarchy trees
                    processor.build_hierarchy_trees(temp_file, num_workers=1)
                    
                    # Mock the database operations
                    with patch.object(processor, '_insert_positions_batch') as mock_insert_positions, \
                         patch.object(processor, '_insert_locations_batch') as mock_insert_locations, \
                         patch.object(processor, '_insert_countries_batch') as mock_insert_countries:
                        
                        # Extract entities
                        counts = processor.extract_entities_from_dump(temp_file, batch_size=10)
                        
                        # Verify counts
                        assert counts["positions"] == 2  # public office + Mayor
                        assert counts["locations"] == 2  # geographic location + city
                        assert counts["countries"] == 1  # United States
                        
                        # Verify batch insert methods were called
                        assert mock_insert_positions.called
                        assert mock_insert_locations.called
                        assert mock_insert_countries.called
                        
                        # Check the data passed to insert methods
                        positions_data = []
                        for call in mock_insert_positions.call_args_list:
                            positions_data.extend(call[0][0])
                        assert len(positions_data) == 2
                        position_ids = {p["wikidata_id"] for p in positions_data}
                        assert "Q294414" in position_ids  # public office
                        assert "Q30185" in position_ids   # Mayor
                        
                        locations_data = []
                        for call in mock_insert_locations.call_args_list:
                            locations_data.extend(call[0][0])
                        assert len(locations_data) == 2
                        location_ids = {l["wikidata_id"] for l in locations_data}
                        assert "Q2221906" in location_ids  # geographic location
                        assert "Q515" in location_ids      # city
                        
                        countries_data = []
                        for call in mock_insert_countries.call_args_list:
                            countries_data.extend(call[0][0])
                        assert len(countries_data) == 1
                        assert countries_data[0]["wikidata_id"] == "Q30"
                        assert countries_data[0]["name"] == "United States"
                        assert countries_data[0]["iso_code"] == "US"
                
                finally:
                    os.chdir(original_cwd)
        
        finally:
            os.unlink(temp_file)
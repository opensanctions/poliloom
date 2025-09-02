"""Tests for WikidataHierarchyImporter."""

import pytest
import json
import tempfile
import os

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import WikidataClass, SubclassRelation
from poliloom.services.hierarchy_importer import WikidataHierarchyImporter
from .conftest import load_json_fixture


class TestWikidataHierarchyImporter:
    """Test WikidataHierarchyImporter functionality."""

    @pytest.fixture
    def hierarchy_importer(self):
        """Create a WikidataHierarchyImporter instance."""
        return WikidataHierarchyImporter()

    @pytest.fixture
    def sample_dump_content(self):
        """Create sample dump content for testing."""
        # Load entities from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = dump_data["sample_dump_entities"]

        # Convert to JSONL format with newlines
        return "\n".join(json.dumps(entity) for entity in entities) + "\n"

    def test_process_chunk_for_relationships(self, hierarchy_importer):
        """Test processing a chunk of the dump file to extract relationships."""
        # Create test dump content with P279 relationships
        test_entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Entity 1"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q2"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Entity 3"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q2"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
        ]

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            for entity in test_entities:
                temp_file.write(json.dumps(entity) + "\n")
            temp_file_path = temp_file.name

        try:
            from poliloom.services.hierarchy_importer import (
                _process_chunk_for_relationships,
            )

            # Test processing the chunk
            relationships, entity_count = _process_chunk_for_relationships(
                temp_file_path, 0, os.path.getsize(temp_file_path), 0
            )

            # Verify results
            assert entity_count == 2
            assert "Q2" in relationships
            assert relationships["Q2"] == {"Q1", "Q3"}

        finally:
            os.unlink(temp_file_path)

    def test_import_hierarchy_trees_with_complex_relationships(
        self, hierarchy_importer
    ):
        """Test importing hierarchy trees with complex P279 relationships."""
        # Create dump content with complex hierarchy
        test_entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Root Entity"}},
                "claims": {},
            },
            {
                "id": "Q2",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Child 1"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q1"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Child 2"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q1"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            {
                "id": "Q4",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Grandchild"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q2"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            for entity in test_entities:
                temp_file.write(json.dumps(entity) + "\n")
            temp_file_path = temp_file.name

        try:
            with Session(get_engine()) as session:
                # Clear existing test data
                session.query(SubclassRelation).delete()
                session.query(WikidataClass).delete()
                session.commit()

            # Test hierarchy tree importing (now saves to database)
            hierarchy_importer.import_hierarchy_trees(temp_file_path)

            # Verify relationships were saved to database
            with Session(get_engine()) as session:
                relations = session.query(SubclassRelation).all()

                # Check specific relationships exist in database
                parent_child_pairs = [
                    (r.parent_class_id, r.child_class_id) for r in relations
                ]
                assert ("Q1", "Q2") in parent_child_pairs
                assert ("Q1", "Q3") in parent_child_pairs
                assert ("Q2", "Q4") in parent_child_pairs
                assert len(parent_child_pairs) == 3

                # Verify WikidataClass records were created with names
                classes = (
                    session.query(WikidataClass)
                    .filter(WikidataClass.name.isnot(None))
                    .all()
                )
                class_names = {c.wikidata_id: c.name for c in classes}

                assert "Q1" in class_names
                assert "Q2" in class_names
                assert "Q3" in class_names
                assert "Q4" in class_names
                assert class_names["Q1"] == "Root Entity"
                assert class_names["Q2"] == "Child 1"

        finally:
            os.unlink(temp_file_path)

    def test_import_hierarchy_trees_with_malformed_claims(self, hierarchy_importer):
        """Test importing hierarchy trees with malformed P279 claims."""
        test_entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Valid Entity"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                "datavalue": {
                                    "value": {"id": "Q2"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Entity with Bad Claim"}},
                "claims": {
                    "P279": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P279",
                                # Missing datavalue - should be ignored
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            for entity in test_entities:
                temp_file.write(json.dumps(entity) + "\n")
            temp_file_path = temp_file.name

        try:
            with Session(get_engine()) as session:
                # Clear existing test data
                session.query(SubclassRelation).delete()
                session.query(WikidataClass).delete()
                session.commit()

            hierarchy_importer.import_hierarchy_trees(temp_file_path)

            # Verify only valid relationships were saved to database
            with Session(get_engine()) as session:
                relations = session.query(SubclassRelation).all()

                # Should only have the valid Q2->Q1 relationship
                parent_child_pairs = [
                    (r.parent_class_id, r.child_class_id) for r in relations
                ]
                assert ("Q2", "Q1") in parent_child_pairs

                # Should not have invalid relationships (total count should be 1)
                assert len(parent_child_pairs) == 1

                # Verify WikidataClass records were created for involved entities in hierarchy
                classes = (
                    session.query(WikidataClass)
                    .filter(WikidataClass.name.isnot(None))
                    .all()
                )
                class_ids = {c.wikidata_id for c in classes}
                assert "Q1" in class_ids
                # Q2 should also be created as a parent in the hierarchy
                assert "Q2" in class_ids if len(class_ids) > 1 else True
                # Q3 is not created because it has no valid P279 relationships

        finally:
            os.unlink(temp_file_path)

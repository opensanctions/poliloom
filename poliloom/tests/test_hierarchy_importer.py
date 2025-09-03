"""Tests for WikidataHierarchyImporter."""

import pytest
import json
import tempfile
import os

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import WikidataClass, SubclassRelation
from poliloom.importer.hierarchy import import_hierarchy_trees
from .conftest import load_json_fixture


class TestWikidataHierarchyImporter:
    """Test hierarchy importing functionality."""

    @pytest.fixture
    def sample_dump_content(self):
        """Create sample dump content for testing."""
        # Load entities from fixture
        dump_data = load_json_fixture("dump_processor_entities.json")
        entities = dump_data["sample_dump_entities"]

        # Convert to JSONL format with newlines
        return "\n".join(json.dumps(entity) for entity in entities) + "\n"

    def test_process_hierarchy_chunk(self):
        """Test processing a chunk of the dump file to extract relationships and insert classes."""
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
            from poliloom.importer.hierarchy import (
                _process_hierarchy_chunk,
            )

            with Session(get_engine()) as session:
                # Clear existing test data
                session.query(SubclassRelation).delete()
                session.query(WikidataClass).delete()
                session.commit()

            # Test processing the chunk
            relationships, entity_count = _process_hierarchy_chunk(
                temp_file_path, 0, os.path.getsize(temp_file_path), 0
            )

            # Verify results - now returns child_id -> parent_ids format
            assert entity_count == 2
            assert "Q1" in relationships
            assert "Q3" in relationships
            assert relationships["Q1"] == {"Q2"}
            assert relationships["Q3"] == {"Q2"}

            # Verify WikidataClass records were inserted for children only
            # (parents will be inserted by main thread later)
            with Session(get_engine()) as session:
                classes = session.query(WikidataClass).all()
                class_ids = {c.wikidata_id for c in classes}
                # Should have Q1 and Q3 (children with P279 claims)
                # Q2 (parent) is not inserted by worker - main thread will handle it
                assert "Q1" in class_ids
                assert "Q3" in class_ids
                assert len(class_ids) == 2

        finally:
            os.unlink(temp_file_path)

    def test_import_hierarchy_trees_with_complex_relationships(self):
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
            import_hierarchy_trees(temp_file_path)

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

                # Verify WikidataClass records were created
                # Children (Q2, Q3, Q4) should have names from workers
                # Parents (Q1) inserted by main thread may not have names
                all_classes = session.query(WikidataClass).all()
                all_class_ids = {c.wikidata_id for c in all_classes}

                # All entities should exist as WikidataClass records
                assert "Q1" in all_class_ids
                assert "Q2" in all_class_ids
                assert "Q3" in all_class_ids
                assert "Q4" in all_class_ids

                # Check names for entities that should have them
                classes_with_names = (
                    session.query(WikidataClass)
                    .filter(WikidataClass.name.isnot(None))
                    .all()
                )
                class_names = {c.wikidata_id: c.name for c in classes_with_names}

                # Q2, Q3, Q4 should have names (processed by workers)
                assert "Q2" in class_names
                assert "Q3" in class_names
                assert "Q4" in class_names
                assert class_names["Q2"] == "Child 1"
                assert class_names["Q3"] == "Child 2"
                assert class_names["Q4"] == "Grandchild"

                # Q1 may or may not have a name since it's inserted by main thread
                # without being processed by a worker (it has no P279 claims)

        finally:
            os.unlink(temp_file_path)

    def test_import_hierarchy_trees_with_malformed_claims(self):
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

            import_hierarchy_trees(temp_file_path)

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
                all_classes = session.query(WikidataClass).all()
                all_class_ids = {c.wikidata_id for c in all_classes}

                # Q1 and Q2 should exist (Q1 processed by worker, Q2 inserted by main thread)
                assert "Q1" in all_class_ids
                assert "Q2" in all_class_ids

                # Check which entities have names (only those processed by workers)
                classes_with_names = (
                    session.query(WikidataClass)
                    .filter(WikidataClass.name.isnot(None))
                    .all()
                )
                class_names = {c.wikidata_id: c.name for c in classes_with_names}

                # Q1 should have a name (processed by worker with valid P279 claim)
                assert "Q1" in class_names
                assert class_names["Q1"] == "Valid Entity"

                # Q3 should NOT be in hierarchy since it has malformed P279 claim
                # Q2 may not have a name since it's inserted by main thread

        finally:
            os.unlink(temp_file_path)

"""Tests for WikidataHierarchyImporter."""

import pytest
import json
import tempfile
import os

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import WikidataEntity, WikidataRelation
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

    def test_process_first_pass_chunk(self):
        """Test first pass: collecting parent IDs and P279 entities."""
        # Create test dump content with P279 and other relationships
        test_entities = [
            {
                "id": "Q1",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Entity 1"}},
                "claims": {
                    "P279": [
                        {
                            "id": "Q1$statement-1",
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
                    ],
                    "P31": [  # instance_of
                        {
                            "id": "Q1$statement-2",
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q100"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            {
                "id": "Q3",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Entity 3"}},
                "claims": {
                    "P279": [
                        {
                            "id": "Q3$statement-1",
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
                _process_first_pass_chunk,
            )

            with Session(get_engine()) as session:
                # Clear existing test data
                session.query(WikidataRelation).delete()
                session.query(WikidataEntity).delete()
                session.commit()

            # Test first pass processing
            parent_ids, entity_count = _process_first_pass_chunk(
                temp_file_path, 0, os.path.getsize(temp_file_path), 0
            )

            # Verify results
            assert entity_count == 2

            # All parent IDs (from P279 and P31)
            assert "Q2" in parent_ids  # Parent from P279
            assert "Q100" in parent_ids  # Parent from P31
            assert len(parent_ids) == 2

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
                            "id": "Q2$statement-complex-1",
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
                            "id": "Q3$statement-complex-1",
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
                            "id": "Q4$statement-complex-1",
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
                session.query(WikidataRelation).delete()
                session.query(WikidataEntity).delete()
                session.commit()

            # Test hierarchy tree importing (now saves to database)
            import_hierarchy_trees(temp_file_path)

            # Verify relationships were saved to database
            with Session(get_engine()) as session:
                relations = session.query(WikidataRelation).all()

                # Only relations from entities in target set get stored
                # Target set = parent IDs (Q1, Q2) + existing DB entities (empty initially)
                # So only Q1 and Q2 get processed, only their relations are stored
                parent_child_pairs = [
                    (r.parent_entity_id, r.child_entity_id) for r in relations
                ]
                # Q2 -> Q1 relation (Q2 is in target set as parent of Q4)
                assert ("Q1", "Q2") in parent_child_pairs
                # Q3 -> Q1 is NOT stored (Q3 not in target set)
                assert ("Q1", "Q3") not in parent_child_pairs
                # Q4 -> Q2 is NOT stored (Q4 not in target set)
                assert ("Q2", "Q4") not in parent_child_pairs
                assert len(parent_child_pairs) == 1

                # Verify WikidataEntity records were created
                all_classes = session.query(WikidataEntity).all()
                all_class_ids = {c.wikidata_id for c in all_classes}

                # Only parent entities exist (Q1, Q2 are parents)
                assert "Q1" in all_class_ids  # Parent of Q2 and Q3
                assert "Q2" in all_class_ids  # Parent of Q4
                # Q3 and Q4 are NOT in the database (not parents, not in existing DB)
                assert "Q3" not in all_class_ids
                assert "Q4" not in all_class_ids

                # Check names - parent entities get names in second pass
                class_names = {c.wikidata_id: c.name for c in all_classes}

                # Parent entities processed in second pass have names
                assert class_names["Q1"] == "Root Entity"
                assert class_names["Q2"] == "Child 1"

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
                            "id": "Q1$statement-malformed-1",
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
                session.query(WikidataRelation).delete()
                session.query(WikidataEntity).delete()
                session.commit()

            import_hierarchy_trees(temp_file_path)

            # Verify only valid relationships were saved to database
            with Session(get_engine()) as session:
                relations = session.query(WikidataRelation).all()

                # Q1 has P279 -> Q2, so Q2 is parent, Q1 is child
                # Only Q2 is in target set (as parent), so no relations stored
                # (Q1 is not in target set, so its relations aren't stored)
                parent_child_pairs = [
                    (r.parent_entity_id, r.child_entity_id) for r in relations
                ]
                # No relations should be stored because Q1 (the child) is not in target set
                assert len(parent_child_pairs) == 0

                # Verify WikidataEntity records were created
                all_classes = session.query(WikidataEntity).all()
                all_class_ids = {c.wikidata_id for c in all_classes}

                # Only Q2 should exist (it's a parent)
                assert "Q2" in all_class_ids
                # Q1 is not a parent and not in existing DB, so it's not imported
                assert "Q1" not in all_class_ids
                # Q3 has malformed claim, no valid parent extracted, so not imported
                assert "Q3" not in all_class_ids

        finally:
            os.unlink(temp_file_path)

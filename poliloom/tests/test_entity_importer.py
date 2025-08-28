"""Tests for WikidataEntityImporter."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch

from poliloom.models import WikidataClass, SubclassRelation, Position, Location, Country
from poliloom.services.entity_importer import WikidataEntityImporter
from sqlalchemy.dialects.postgresql import insert


class TestWikidataEntityImporter:
    """Test WikidataEntityImporter functionality."""

    @pytest.fixture
    def entity_importer(self):
        """Create a WikidataEntityImporter instance."""
        return WikidataEntityImporter()

    def test_extract_entities_from_dump_integration(self, entity_importer, db_session):
        """Test complete entity extraction workflow integration."""

        # First, set up hierarchy in database using current approach
        hierarchy_data = [
            # Position hierarchy: Q294414 (position) -> Q4164871 (office)
            {"wikidata_id": "Q294414", "name": "position"},  # Root position class
            {
                "wikidata_id": "Q4164871",
                "name": "office",
            },  # Office (subclass of position)
            # Location hierarchy: Q2221906 (location) -> Q515 (city)
            {
                "wikidata_id": "Q2221906",
                "name": "geographic location",
            },  # Root location class
            {"wikidata_id": "Q515", "name": "city"},  # City (subclass of location)
        ]

        hierarchy_relations = [
            {"parent_class_id": "Q294414", "child_class_id": "Q4164871"},
            {"parent_class_id": "Q2221906", "child_class_id": "Q515"},
        ]

        # Insert hierarchy data first
        stmt = insert(WikidataClass).values(hierarchy_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(SubclassRelation).values(hierarchy_relations)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_subclass_parent_child")
        db_session.execute(stmt)
        db_session.commit()

        # Create test entities covering all types we extract
        test_entities = [
            # Position entity - should be extracted
            {
                "id": "Q123456",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Office Position"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q4164871"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            # Location entity - should be extracted
            {
                "id": "Q789012",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test City Location"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q515"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            # Country entity - should be extracted
            {
                "id": "Q345678",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Country"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q6256"},
                                    "type": "wikibase-entityid",
                                },  # country
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P297": [
                        {  # ISO 3166-1 alpha-2 code
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P297",
                                "datavalue": {"value": "TC", "type": "string"},
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Politician entity - should be ignored (wrong type for this extractor)
            {
                "id": "Q999999",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Politician"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q5"},
                                    "type": "wikibase-entityid",
                                },  # human
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P106": [
                        {  # occupation
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P106",
                                "datavalue": {
                                    "value": {"id": "Q82955"},
                                    "type": "wikibase-entityid",
                                },  # politician
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Entity without name - should be ignored
            {
                "id": "Q111111",
                "type": "item",
                "labels": {},  # No labels/name
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q4164871"},
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

        # Create temporary dump file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            for entity in test_entities:
                temp_file.write(json.dumps(entity) + "\n")
            temp_file_path = temp_file.name

        try:
            # Clear existing entity data
            db_session.query(Position).delete()
            db_session.query(Location).delete()
            db_session.query(Country).delete()
            db_session.commit()

            # Test extraction
            with patch.object(
                entity_importer.dump_reader, "calculate_file_chunks"
            ) as mock_chunks:
                # Mock chunks to return single chunk for simpler testing
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]

                result = entity_importer.extract_entities_from_dump(
                    temp_file_path, batch_size=10
                )

            # Verify counts returned
            assert result["positions"] == 1
            assert result["locations"] == 1
            assert result["countries"] == 1

            # Verify entities were actually saved to database
            positions = db_session.query(Position).all()
            locations = db_session.query(Location).all()
            countries = db_session.query(Country).all()

            assert len(positions) == 1
            assert len(locations) == 1
            assert len(countries) == 1

            # Verify specific entity data
            position = positions[0]
            assert position.wikidata_id == "Q123456"
            assert position.name == "Test Office Position"
            assert position.wikidata_class_id == "Q4164871"

            location = locations[0]
            assert location.wikidata_id == "Q789012"
            assert location.name == "Test City Location"
            assert location.wikidata_class_id == "Q515"

            country = countries[0]
            assert country.wikidata_id == "Q345678"
            assert country.name == "Test Country"
            assert country.iso_code == "TC"

        finally:
            os.unlink(temp_file_path)

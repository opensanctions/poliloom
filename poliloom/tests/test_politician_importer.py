"""Tests for WikidataPoliticianImporter."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import Politician
from poliloom.services.politician_importer import WikidataPoliticianImporter


class TestWikidataPoliticianImporter:
    """Test WikidataPoliticianImporter functionality."""

    @pytest.fixture
    def politician_importer(self):
        """Create a WikidataPoliticianImporter instance."""
        return WikidataPoliticianImporter()

    def test_extract_politicians_from_dump_integration(self, politician_importer):
        """Test complete politician extraction workflow integration."""

        # Create test entities
        test_entities = [
            # Living politician - should be included
            {
                "id": "Q123456",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Living Politician"}},
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
            # Recently deceased politician (died 2020) - should be included
            {
                "id": "Q789012",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Recent Politician"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q5"},
                                    "type": "wikibase-entityid",
                                },
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
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P570": [
                        {  # date of death
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P570",
                                "datavalue": {
                                    "value": {
                                        "time": "+2020-05-15T00:00:00Z",
                                        "timezone": 0,
                                        "before": 0,
                                        "after": 0,
                                        "precision": 11,  # day precision
                                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                    },
                                    "type": "time",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Old deceased politician (died 1945) - should be excluded
            {
                "id": "Q345678",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Old Politician"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q5"},
                                    "type": "wikibase-entityid",
                                },
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
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P570": [
                        {  # date of death
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P570",
                                "datavalue": {
                                    "value": {
                                        "time": "+1945-04-12T00:00:00Z",
                                        "timezone": 0,
                                        "before": 0,
                                        "after": 0,
                                        "precision": 11,  # day precision
                                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                    },
                                    "type": "time",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Non-politician human - should be excluded
            {
                "id": "Q999999",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Regular Person"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q5"},
                                    "type": "wikibase-entityid",
                                },
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
                                    "value": {"id": "Q40348"},
                                    "type": "wikibase-entityid",
                                },  # lawyer
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Non-human entity - should be excluded
            {
                "id": "Q111111",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Some Organization"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q43229"},
                                    "type": "wikibase-entityid",
                                },  # organization
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
            # Clear existing politician data
            with Session(get_engine()) as session:
                session.query(Politician).delete()
                session.commit()

            # Test extraction
            with patch.object(
                politician_importer.dump_reader, "calculate_file_chunks"
            ) as mock_chunks:
                # Mock chunks to return single chunk for simpler testing
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]

                result = politician_importer.extract_politicians_from_dump(
                    temp_file_path, batch_size=10
                )

            # Verify count returned (should be 2: living politician + recently deceased)
            assert result == 2

            # Verify politicians were actually saved to database
            with Session(get_engine()) as session:
                politicians = session.query(Politician).all()
                assert len(politicians) == 2

                # Verify specific politician data
                politician_ids = {p.wikidata_id for p in politicians}
                assert "Q123456" in politician_ids  # Living politician
                assert "Q789012" in politician_ids  # Recently deceased
                assert "Q345678" not in politician_ids  # Old deceased - excluded
                assert "Q999999" not in politician_ids  # Non-politician - excluded
                assert "Q111111" not in politician_ids  # Non-human - excluded

                # Verify names were saved correctly
                politician_names = {p.wikidata_id: p.name for p in politicians}
                assert politician_names["Q123456"] == "Living Politician"
                assert politician_names["Q789012"] == "Recent Politician"

        finally:
            os.unlink(temp_file_path)

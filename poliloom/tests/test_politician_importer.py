"""Tests for WikidataPoliticianImporter."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import (
    Politician,
    Position,
    Location,
    Country,
    Property,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    WikipediaLink,
)
from poliloom.services.politician_importer import (
    WikidataPoliticianImporter,
    _insert_politicians_batch,
)


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

    def test_insert_politicians_batch_basic(self, db_session):
        """Test inserting a batch of politicians with basic data."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "positions": [],
                "citizenships": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "properties": [],
                "positions": [],
                "citizenships": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
        ]

        _insert_politicians_batch(politicians)

        # Verify politicians were inserted
        inserted_politicians = db_session.query(Politician).all()
        assert len(inserted_politicians) == 2
        wikidata_ids = {pol.wikidata_id for pol in inserted_politicians}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_politicians_batch_with_duplicates(self, db_session):
        """Test inserting politicians with some duplicates."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "positions": [],
                "citizenships": [],
                "birthplace": None,
                "wikipedia_links": [],
            }
        ]

        # Insert first batch
        _insert_politicians_batch(politicians)

        # Insert again with updated name - should update
        updated_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe Updated",
                "properties": [],
                "positions": [],
                "citizenships": [],
                "birthplace": None,
                "wikipedia_links": [],
            }
        ]
        _insert_politicians_batch(updated_politicians)

        # Should still have only 1 politician with updated name
        final_politicians = db_session.query(Politician).all()
        assert len(final_politicians) == 1
        assert final_politicians[0].wikidata_id == "Q1"
        assert final_politicians[0].name == "John Doe Updated"

    def test_insert_politicians_batch_empty(self, db_session):
        """Test inserting empty batch of politicians."""
        politicians = []

        # Should handle empty batch gracefully without errors
        _insert_politicians_batch(politicians)

        # Verify no politicians were inserted
        inserted_politicians = db_session.query(Politician).all()
        assert len(inserted_politicians) == 0

    def test_insert_politicians_batch_with_properties(self, db_session):
        """Test inserting politicians with properties."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": "birth_date",
                        "value": "1970-01-01",
                        "value_precision": 11,
                    },
                    {
                        "type": "death_date",
                        "value": "2020-01-01",
                        "value_precision": 11,
                    },
                ],
                "positions": [],
                "citizenships": [],
                "birthplace": None,
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians)

        # Verify politician and properties were created
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None
        assert politician.name == "John Doe"

        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )
        assert len(properties) == 2

        prop_types = {prop.type for prop in properties}
        assert prop_types == {"birth_date", "death_date"}

    def test_insert_politicians_batch_with_relationships(self, db_session):
        """Test inserting politicians with full relationship data."""
        # First create the required related entities
        position1 = Position(name="Mayor", wikidata_id="Q30185")
        position2 = Position(name="President", wikidata_id="Q11696")
        country1 = Country(name="United States", wikidata_id="Q30", iso_code="US")
        country2 = Country(name="Canada", wikidata_id="Q16", iso_code="CA")
        location = Location(name="New York City", wikidata_id="Q60")

        db_session.add_all([position1, position2, country1, country2, location])
        db_session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": "birth_date",
                        "value": "1970-01-01",
                        "value_precision": 11,
                    },
                ],
                "citizenships": ["Q30", "Q16"],  # US and Canada
                "positions": [
                    {
                        "wikidata_id": "Q30185",
                        "start_date": "2020-01-01",
                        "start_date_precision": 11,
                        "end_date": "2024-01-01",
                        "end_date_precision": 11,
                    },
                    {
                        "wikidata_id": "Q11696",
                        "start_date": "2018-01-01",
                        "start_date_precision": 11,
                        "end_date": "2020-01-01",
                        "end_date_precision": 11,
                    },
                ],
                "birthplace": "Q60",
                "wikipedia_links": [
                    {
                        "url": "https://en.wikipedia.org/wiki/John_Doe",
                        "language": "en",
                    },
                    {
                        "url": "https://fr.wikipedia.org/wiki/John_Doe",
                        "language": "fr",
                    },
                ],
            }
        ]

        _insert_politicians_batch(politicians)

        # Verify politician was created with all relationships
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None
        assert politician.name == "John Doe"

        # Check properties
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )
        assert len(properties) == 1
        assert properties[0].type == "birth_date"
        assert properties[0].value == "1970-01-01"

        # Check citizenships
        citizenships = (
            db_session.query(HasCitizenship)
            .filter(HasCitizenship.politician_id == politician.id)
            .all()
        )
        assert len(citizenships) == 2
        citizenship_countries = {c.country.wikidata_id for c in citizenships}
        assert citizenship_countries == {"Q30", "Q16"}

        # Check positions
        positions = (
            db_session.query(HoldsPosition)
            .filter(HoldsPosition.politician_id == politician.id)
            .all()
        )
        assert len(positions) == 2
        position_ids = {p.position.wikidata_id for p in positions}
        assert position_ids == {"Q30185", "Q11696"}

        # Check birthplace
        birthplaces = (
            db_session.query(BornAt).filter(BornAt.politician_id == politician.id).all()
        )
        assert len(birthplaces) == 1
        assert birthplaces[0].location.wikidata_id == "Q60"

        # Check Wikipedia links
        wiki_links = (
            db_session.query(WikipediaLink)
            .filter(WikipediaLink.politician_id == politician.id)
            .all()
        )
        assert len(wiki_links) == 2
        wiki_languages = {w.language_code for w in wiki_links}
        assert wiki_languages == {"en", "fr"}

    def test_insert_politicians_batch_missing_relationships(self, db_session):
        """Test inserting politicians when some related entities don't exist."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "citizenships": ["Q999"],  # Non-existent country
                "positions": [
                    {
                        "wikidata_id": "Q999",  # Non-existent position
                        "start_date": "2020-01-01",
                        "start_date_precision": 11,
                        "end_date": "2024-01-01",
                        "end_date_precision": 11,
                    }
                ],
                "birthplace": "Q999",  # Non-existent location
                "wikipedia_links": [],
            }
        ]

        # Should handle missing relationships gracefully
        _insert_politicians_batch(politicians)

        # Verify politician was still created (relationships are optional)
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None
        assert politician.name == "John Doe"

        # Verify no relationships were created for non-existent entities
        citizenships = (
            db_session.query(HasCitizenship)
            .filter(HasCitizenship.politician_id == politician.id)
            .all()
        )
        assert len(citizenships) == 0

        positions = (
            db_session.query(HoldsPosition)
            .filter(HoldsPosition.politician_id == politician.id)
            .all()
        )
        assert len(positions) == 0

        birthplaces = (
            db_session.query(BornAt).filter(BornAt.politician_id == politician.id).all()
        )
        assert len(birthplaces) == 0

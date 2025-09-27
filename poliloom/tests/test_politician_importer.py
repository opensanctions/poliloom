"""Tests for WikidataPoliticianImporter."""

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
    PropertyType,
    WikipediaLink,
)
from poliloom.importer.politician import (
    import_politicians,
    _insert_politicians_batch,
    _is_politician,
    _should_import_politician,
)
from poliloom.wikidata_entity_processor import WikidataEntityProcessor
from poliloom.wikidata_date import WikidataDate


class TestWikidataPoliticianImporter:
    """Test politician importing functionality."""

    def test_import_politicians_integration(self):
        """Test complete politician extraction workflow."""

        # Create simple test entity - focus on integration rather than filtering logic
        test_entities = [
            {
                "id": "Q123456",
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
            with patch("poliloom.dump_reader.calculate_file_chunks") as mock_chunks:
                # Mock chunks to return single chunk for simpler testing
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]

                import_politicians(temp_file_path, batch_size=10)

            # Verify politician was actually saved to database
            with Session(get_engine()) as session:
                politicians = session.query(Politician).all()
                assert len(politicians) == 1
                assert politicians[0].wikidata_id == "Q123456"
                assert politicians[0].name == "Test Politician"

        finally:
            os.unlink(temp_file_path)

    def test_insert_politicians_batch_basic(self, db_session):
        """Test inserting a batch of politicians with basic data."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "properties": [],
                "wikipedia_links": [],
            },
        ]

        _insert_politicians_batch(politicians, get_engine())

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
                "wikipedia_links": [],
            }
        ]

        # Insert first batch
        _insert_politicians_batch(politicians, get_engine())

        # Insert again with updated name - should update
        updated_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe Updated",
                "properties": [],
                "wikipedia_links": [],
            }
        ]
        _insert_politicians_batch(updated_politicians, get_engine())

        # Should still have only 1 politician with updated name
        final_politicians = db_session.query(Politician).all()
        assert len(final_politicians) == 1
        assert final_politicians[0].wikidata_id == "Q1"
        assert final_politicians[0].name == "John Doe Updated"

    def test_insert_politicians_batch_empty(self, db_session):
        """Test inserting empty batch of politicians."""
        politicians = []

        # Should handle empty batch gracefully without errors
        _insert_politicians_batch(politicians, get_engine())

        # Verify no politicians were inserted
        inserted_politicians = db_session.query(Politician).all()
        assert len(inserted_politicians) == 0

    def test_import_birth_date(self, db_session):
        """Test importing birth date from Wikidata claim."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "1950-05-15",
                        "value_precision": 11,
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        # Verify politician and property created correctly
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None
        assert politician.name == "John Doe"

        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .filter(Property.type == PropertyType.BIRTH_DATE)
            .all()
        )

        assert len(properties) == 1
        prop = properties[0]
        assert prop.value == "1950-05-15"
        assert prop.value_precision == 11
        assert prop.entity_id is None
        assert prop.statement_id == "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A"

    def test_import_position(self, db_session):
        """Test importing position from Wikidata claim."""
        # Create position first
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.POSITION,
                        "entity_id": "Q30185",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C81",
                        "qualifiers_json": {
                            "P580": [
                                WikidataDate.from_date_string(
                                    "2020-01-01"
                                ).to_wikidata_qualifier()
                            ],
                            "P582": [
                                WikidataDate.from_date_string(
                                    "2024-01-01"
                                ).to_wikidata_qualifier()
                            ],
                        },
                        "references_json": None,
                    }
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        # Verify property created correctly
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .filter(Property.type == PropertyType.POSITION)
            .all()
        )

        assert len(properties) == 1
        prop = properties[0]
        assert prop.entity_id == "Q30185"
        assert prop.value is None
        # Check qualifiers contain start/end dates
        assert "P580" in prop.qualifiers_json  # start date
        assert "P582" in prop.qualifiers_json  # end date

    def test_import_birthplace(self, db_session):
        """Test importing birthplace from Wikidata claim."""
        # Create location first
        Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.BIRTHPLACE,
                        "entity_id": "Q60",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C83",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .filter(Property.type == PropertyType.BIRTHPLACE)
            .all()
        )

        assert len(properties) == 1
        assert properties[0].entity_id == "Q60"

    def test_import_citizenship(self, db_session):
        """Test importing citizenship from Wikidata claim."""
        # Create country first
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.CITIZENSHIP,
                        "entity_id": "Q30",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C84",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .filter(Property.type == PropertyType.CITIZENSHIP)
            .all()
        )

        assert len(properties) == 1
        assert properties[0].entity_id == "Q30"

    def test_import_all_properties(self, db_session):
        """Test importing all property types for a politician."""
        # Create required entities
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        Location.create_with_entity(db_session, "Q60", "New York City")
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "1970-01-01",
                        "value_precision": 11,
                        "entity_id": None,
                        "statement_id": "Q1$BIRTH",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                    {
                        "type": PropertyType.DEATH_DATE,
                        "value": "2020-01-01",
                        "value_precision": 11,
                        "entity_id": None,
                        "statement_id": "Q1$DEATH",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                    {
                        "type": PropertyType.POSITION,
                        "value": None,
                        "value_precision": None,
                        "entity_id": "Q30185",
                        "statement_id": "Q1$POSITION",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                    {
                        "type": PropertyType.BIRTHPLACE,
                        "value": None,
                        "value_precision": None,
                        "entity_id": "Q60",
                        "statement_id": "Q1$BIRTHPLACE",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                    {
                        "type": PropertyType.CITIZENSHIP,
                        "value": None,
                        "value_precision": None,
                        "entity_id": "Q30",
                        "statement_id": "Q1$CITIZENSHIP",
                        "qualifiers_json": None,
                        "references_json": None,
                    },
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        # Verify all properties created
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        all_props = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )

        # Group by type
        props_by_type = {}
        for prop in all_props:
            props_by_type.setdefault(prop.type, []).append(prop)

        assert PropertyType.BIRTH_DATE in props_by_type
        assert PropertyType.DEATH_DATE in props_by_type
        assert PropertyType.POSITION in props_by_type
        assert PropertyType.BIRTHPLACE in props_by_type
        assert PropertyType.CITIZENSHIP in props_by_type

    def test_preserve_statement_metadata(self, db_session):
        """Test that statement_id, qualifiers, and references are preserved."""
        expected_qualifiers = {"P580": [{"test": "qualifier"}]}
        expected_references = {"test": "reference"}

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "1970-01-01",
                        "value_precision": 11,
                        "statement_id": "Q1$TEST_STATEMENT",
                        "qualifiers_json": expected_qualifiers,
                        "references_json": expected_references,
                    }
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        prop = db_session.query(Property).first()
        assert prop.statement_id == "Q1$TEST_STATEMENT"
        assert prop.qualifiers_json == expected_qualifiers
        assert prop.references_json == expected_references

    def test_insert_politicians_batch_with_wikipedia_links(self, db_session):
        """Test inserting politicians with Wikipedia links."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
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

        _insert_politicians_batch(politicians, get_engine())

        # Verify politician was created with Wikipedia links
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        # Check Wikipedia links
        wiki_links = (
            db_session.query(WikipediaLink)
            .filter(WikipediaLink.politician_id == politician.id)
            .all()
        )
        assert len(wiki_links) == 2
        wiki_languages = {w.iso_code for w in wiki_links}
        assert wiki_languages == {"en", "fr"}


class TestIsPolitician:
    """Test the _is_politician helper function."""

    def test_is_politician_by_occupation(self):
        """Test politician identification by occupation P106=Q82955."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q5"}},
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q82955"}},  # politician
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

        assert _is_politician(entity, relevant_positions) is True

    def test_is_politician_by_position(self):
        """Test politician identification by position held."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q5"}},
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q40348"}},  # lawyer
                        },
                    }
                ],
                "P39": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q30185"}},  # mayor
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])  # mayor is relevant

        assert _is_politician(entity, relevant_positions) is True

    def test_not_politician_non_human(self):
        """Test that non-human entities are not considered politicians."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q43229"}},  # organization
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q82955"}},  # politician
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

        assert _is_politician(entity, relevant_positions) is False

    def test_not_politician_no_relevant_occupation_or_position(self):
        """Test that humans without politician occupation or relevant positions are not politicians."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q5"}},  # human
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q40348"}},  # lawyer
                        },
                    }
                ],
                "P39": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q99999"}
                            },  # irrelevant position
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(
            ["Q30185"]
        )  # mayor is relevant, but entity doesn't have it

        assert _is_politician(entity, relevant_positions) is False

    def test_is_politician_malformed_claims(self):
        """Test politician identification handles malformed claims gracefully."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q5"}},  # human
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            # Missing datavalue - should be handled gracefully
                        },
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q82955"}},  # politician
                        },
                    },
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

        # Should still identify as politician despite malformed first claim
        assert _is_politician(entity, relevant_positions) is True

    def test_is_politician_empty_claims(self):
        """Test politician identification with missing or empty claims."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q5"}},  # human
                        },
                    }
                ],
                # No P106 or P39 claims
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

        assert _is_politician(entity, relevant_positions) is False


class TestShouldImportPolitician:
    """Test the _should_import_politician helper function."""

    def test_should_import_living_politician(self):
        """Test that living politicians should be imported."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P569": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "+1980-05-15T00:00:00Z",
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        assert _should_import_politician(entity) is True

    def test_should_not_import_ancient_living_politician(self):
        """Test that living politicians born over 120 years ago should not be imported."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P569": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "+1800-05-15T00:00:00Z",
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        assert _should_import_politician(entity) is False

    def test_should_import_recently_deceased_politician(self):
        """Test that recently deceased politicians should be imported."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "+2023-05-15T00:00:00Z",
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        assert _should_import_politician(entity) is True

    def test_should_not_import_old_deceased_politician(self):
        """Test that old deceased politicians should not be imported."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "+1945-04-12T00:00:00Z",
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        assert _should_import_politician(entity) is False

    def test_should_not_import_bce_dates(self):
        """Test that politicians with BCE birth/death dates should not be imported."""
        # Entity with BCE death date
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "-0044-03-15T00:00:00Z",  # BCE date
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        assert _should_import_politician(entity) is False

    def test_should_import_with_malformed_dates(self):
        """Test that politicians with malformed dates should be imported (default to include)."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P569": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "invalid-date",  # Malformed date
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        # Should default to including politicians when dates can't be parsed
        assert _should_import_politician(entity) is True

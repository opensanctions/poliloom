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
    HoldsPosition,
    HasCitizenship,
    BornAt,
    WikipediaLink,
)
from poliloom.importer.politician import (
    import_politicians,
    _insert_politicians_batch,
    _is_politician,
    _should_import_politician,
)
from poliloom.wikidata_entity_processor import WikidataEntityProcessor


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

                result = import_politicians(temp_file_path, batch_size=10)

            # Verify count returned
            assert result == 1

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
                "positions": [],
                "citizenships": [],
                "birthplaces": [],
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "properties": [],
                "positions": [],
                "citizenships": [],
                "birthplaces": [],
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
                "positions": [],
                "citizenships": [],
                "birthplaces": [],
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
                "positions": [],
                "citizenships": [],
                "birthplaces": [],
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
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A",
                    },
                    {
                        "type": "death_date",
                        "value": "2020-01-01",
                        "value_precision": 11,
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8B",
                    },
                ],
                "positions": [],
                "citizenships": [],
                "birthplaces": [],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

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
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        Position.create_with_entity(db_session, "Q11696", "President")
        Country.create_with_entity(db_session, "Q30", "United States", "US")
        Country.create_with_entity(db_session, "Q16", "Canada", "CA")
        Location.create_with_entity(db_session, "Q60", "New York City")
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
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A",
                        "qualifiers_json": None,  # No qualifiers for this simple birth date
                        "references_json": None,
                    },
                ],
                "citizenships": [
                    {
                        "country_id": "Q30",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C84",
                    },  # US
                    {
                        "country_id": "Q16",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C85",
                    },  # Canada
                ],
                "positions": [
                    {
                        "wikidata_id": "Q30185",
                        "qualifiers_json": {
                            "P580": [
                                {
                                    "datatype": "time",
                                    "snaktype": "value",
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2020-01-01T00:00:00Z",
                                            "after": 0,
                                            "before": 0,
                                            "timezone": 0,
                                            "precision": 11,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        },
                                    },
                                }
                            ],
                            "P582": [
                                {
                                    "datatype": "time",
                                    "snaktype": "value",
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2024-01-01T00:00:00Z",
                                            "after": 0,
                                            "before": 0,
                                            "timezone": 0,
                                            "precision": 11,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        },
                                    },
                                }
                            ],
                        },
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C81",
                    },
                    {
                        "wikidata_id": "Q11696",
                        "qualifiers_json": {
                            "P580": [
                                {
                                    "datatype": "time",
                                    "snaktype": "value",
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2018-01-01T00:00:00Z",
                                            "after": 0,
                                            "before": 0,
                                            "timezone": 0,
                                            "precision": 11,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        },
                                    },
                                }
                            ],
                            "P582": [
                                {
                                    "datatype": "time",
                                    "snaktype": "value",
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2020-01-01T00:00:00Z",
                                            "after": 0,
                                            "before": 0,
                                            "timezone": 0,
                                            "precision": 11,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        },
                                    },
                                }
                            ],
                        },
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C82",
                    },
                ],
                "birthplaces": [
                    {
                        "location_id": "Q60",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C83",
                    }
                ],
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
        assert properties[0].value_precision == 11

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

    def test_insert_politicians_batch_with_qualifiers_json(self, db_session):
        """Test inserting politicians with qualifiers JSON data preservation."""
        # First create the required related entities
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.commit()

        # Test qualifiers data that should be preserved
        position_qualifiers = {
            "P4100": [  # political party
                {
                    "snaktype": "value",
                    "property": "P4100",
                    "datavalue": {
                        "value": {"entity-type": "item", "id": "Q6365037"},
                        "type": "wikibase-entityid",
                    },
                }
            ],
            "P768": [  # electoral district
                {
                    "snaktype": "value",
                    "property": "P768",
                    "datavalue": {
                        "value": {"entity-type": "item", "id": "Q123456"},
                        "type": "wikibase-entityid",
                    },
                }
            ],
            "P580": [  # start time (we also process this specifically)
                {
                    "snaktype": "value",
                    "property": "P580",
                    "datavalue": {
                        "value": {
                            "time": "+2020-01-01T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                        "type": "time",
                    },
                }
            ],
        }

        birthplace_qualifiers = {
            "P585": [  # point in time
                {
                    "snaktype": "value",
                    "property": "P585",
                    "datavalue": {
                        "value": {
                            "time": "+1970-01-01T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                        "type": "time",
                    },
                }
            ],
            "P1480": [  # sourcing circumstances
                {
                    "snaktype": "value",
                    "property": "P1480",
                    "datavalue": {
                        "value": {"entity-type": "item", "id": "Q5727902"},
                        "type": "wikibase-entityid",
                    },
                }
            ],
        }

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "citizenships": [],
                "positions": [
                    {
                        "wikidata_id": "Q30185",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C81",
                        "qualifiers_json": position_qualifiers,
                    }
                ],
                "birthplaces": [
                    {
                        "location_id": "Q60",
                        "statement_id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C83",
                        "qualifiers_json": birthplace_qualifiers,
                    }
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, get_engine())

        # Verify politician was created
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        # Check position with qualifiers_json
        positions = (
            db_session.query(HoldsPosition)
            .filter(HoldsPosition.politician_id == politician.id)
            .all()
        )
        assert len(positions) == 1
        position = positions[0]
        assert position.position.wikidata_id == "Q30185"
        assert position.qualifiers_json is not None

        # Verify all qualifier properties are preserved
        qualifiers = position.qualifiers_json
        assert "P4100" in qualifiers  # political party
        assert "P768" in qualifiers  # electoral district
        assert "P580" in qualifiers  # start time
        assert qualifiers["P4100"][0]["datavalue"]["value"]["id"] == "Q6365037"
        assert qualifiers["P768"][0]["datavalue"]["value"]["id"] == "Q123456"

        # Check birthplace with qualifiers_json
        birthplaces = (
            db_session.query(BornAt).filter(BornAt.politician_id == politician.id).all()
        )
        assert len(birthplaces) == 1
        birthplace = birthplaces[0]
        assert birthplace.location.wikidata_id == "Q60"
        assert birthplace.qualifiers_json is not None

        # Verify all qualifier properties are preserved
        bp_qualifiers = birthplace.qualifiers_json
        assert "P585" in bp_qualifiers  # point in time
        assert "P1480" in bp_qualifiers  # sourcing circumstances
        assert bp_qualifiers["P1480"][0]["datavalue"]["value"]["id"] == "Q5727902"


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

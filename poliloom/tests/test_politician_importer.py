"""Tests for the politician importer."""

from poliloom.importer.politician import (
    _insert_politicians_batch,
    _is_politician,
    _should_import_politician,
)
from poliloom.models import (
    Location,
    Politician,
    Position,
    Statement,
    WikipediaLink,
)
from poliloom.wikidata.entity_processor import WikidataEntityProcessor
from poliloom.wikidata.rest import action_api_statement_to_rest

_CALENDAR_MODEL = "http://www.wikidata.org/entity/Q1985727"


def _time_snak(property_id, time_string, precision=11):
    """Build an Action API time snak as found in the dump."""
    return {
        "snaktype": "value",
        "property": property_id,
        "datatype": "time",
        "datavalue": {
            "value": {
                "time": time_string,
                "timezone": 0,
                "before": 0,
                "after": 0,
                "precision": precision,
                "calendarmodel": _CALENDAR_MODEL,
            },
            "type": "time",
        },
    }


def _time_claim(property_id, statement_id, time_string, precision=11):
    """Build an Action API time claim (P569/P570) as found in the dump."""
    return {
        "id": statement_id,
        "rank": "normal",
        "mainsnak": _time_snak(property_id, time_string, precision),
    }


def _item_claim(property_id, statement_id, entity_id, qualifiers=None):
    """Build an Action API item claim (P19/P27/P39) as found in the dump."""
    claim = {
        "id": statement_id,
        "rank": "normal",
        "mainsnak": {
            "snaktype": "value",
            "property": property_id,
            "datatype": "wikibase-item",
            "datavalue": {
                "value": {
                    "entity-type": "item",
                    "numeric-id": int(entity_id[1:]),
                    "id": entity_id,
                },
                "type": "wikibase-entityid",
            },
        },
    }
    if qualifiers:
        claim["qualifiers"] = qualifiers
        claim["qualifiers-order"] = list(qualifiers)
    return claim


class TestWikidataPoliticianImporter:
    """Test politician importing functionality."""

    def test_insert_politicians_batch_basic(self, db_session):
        """Test inserting a batch of politicians with basic data."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [],
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "statements": [],
                "wikipedia_links": [],
            },
        ]

        _insert_politicians_batch(politicians, db_session)

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
                "statements": [],
                "wikipedia_links": [],
            }
        ]

        # Insert first batch
        _insert_politicians_batch(politicians, db_session)

        # Insert again with updated name - should update
        updated_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe Updated",
                "statements": [],
                "wikipedia_links": [],
            }
        ]
        _insert_politicians_batch(updated_politicians, db_session)

        # Should still have only 1 politician with updated name
        final_politicians = db_session.query(Politician).all()
        assert len(final_politicians) == 1
        assert final_politicians[0].wikidata_id == "Q1"
        assert final_politicians[0].name == "John Doe Updated"

    def test_insert_politicians_batch_empty(self, db_session):
        """Test inserting empty batch of politicians."""
        politicians = []

        # Should handle empty batch gracefully without errors
        _insert_politicians_batch(politicians, db_session)

        # Verify no politicians were inserted
        inserted_politicians = db_session.query(Politician).all()
        assert len(inserted_politicians) == 0

    def test_import_birth_date(self, db_session):
        """Test importing a birth date statement from a Wikidata claim."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _time_claim(
                            "P569",
                            "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A",
                            "+1950-05-15T00:00:00Z",
                        )
                    )
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        # Verify politician and statement created correctly
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None
        assert politician.name == "John Doe"

        statements = (
            db_session.query(Statement)
            .filter(Statement.politician_id == politician.id)
            .all()
        )

        assert len(statements) == 1
        statement = statements[0]
        assert (
            statement.wikidata_statement_id == "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A"
        )
        assert statement.property_id == "P569"
        assert statement.entity_id is None  # P569 has no entity value
        assert statement.document == {
            "id": "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C8A",
            "rank": "normal",
            "property": {"id": "P569", "data_type": "time"},
            "value": {
                "type": "value",
                "content": {
                    "time": "+1950-05-15T00:00:00Z",
                    "precision": 11,
                    "calendarmodel": _CALENDAR_MODEL,
                },
            },
        }

    def test_import_position(self, db_session):
        """Test importing a position statement from a Wikidata claim."""
        # Create position first (statement entity_id references it)
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.flush()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _item_claim(
                            "P39",
                            "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C81",
                            "Q30185",
                            qualifiers={
                                "P580": [_time_snak("P580", "+2020-01-01T00:00:00Z")],
                                "P582": [_time_snak("P582", "+2024-01-01T00:00:00Z")],
                            },
                        )
                    )
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        # Verify statement created correctly
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        statements = (
            db_session.query(Statement)
            .filter(Statement.politician_id == politician.id)
            .all()
        )

        assert len(statements) == 1
        statement = statements[0]
        assert statement.property_id == "P39"
        assert statement.entity_id == "Q30185"
        # Check qualifiers contain start/end dates in REST shape
        qualifier_property_ids = [
            qualifier["property"]["id"]
            for qualifier in statement.document["qualifiers"]
        ]
        assert qualifier_property_ids == ["P580", "P582"]  # start date, end date

    def test_import_birthplace(self, db_session):
        """Test importing a birthplace statement from a Wikidata claim."""
        # Create location first (statement entity_id references it)
        Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.flush()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _item_claim(
                            "P19",
                            "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C83",
                            "Q60",
                        )
                    )
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        statements = (
            db_session.query(Statement)
            .filter(Statement.politician_id == politician.id)
            .all()
        )

        assert len(statements) == 1
        assert statements[0].property_id == "P19"
        assert statements[0].entity_id == "Q60"

    def test_import_citizenship(self, db_session, sample_country):
        """Test importing a citizenship statement from a Wikidata claim."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _item_claim(
                            "P27",
                            "Q1$F1C74569-C9D8-4C53-9F2E-7E16F7BC4C84",
                            "Q30",
                        )
                    )
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        statements = (
            db_session.query(Statement)
            .filter(Statement.politician_id == politician.id)
            .all()
        )

        assert len(statements) == 1
        assert statements[0].property_id == "P27"
        assert statements[0].entity_id == "Q30"

    def test_import_all_property_types(self, db_session, sample_country):
        """Test importing statements for all tracked property types."""
        # Create required entities
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        Location.create_with_entity(db_session, "Q60", "New York City")

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _time_claim("P569", "Q1$BIRTH", "+1970-01-01T00:00:00Z")
                    ),
                    action_api_statement_to_rest(
                        _time_claim("P570", "Q1$DEATH", "+2020-01-01T00:00:00Z")
                    ),
                    action_api_statement_to_rest(
                        _item_claim("P39", "Q1$POSITION", "Q30185")
                    ),
                    action_api_statement_to_rest(
                        _item_claim("P19", "Q1$BIRTHPLACE", "Q60")
                    ),
                    action_api_statement_to_rest(
                        _item_claim("P27", "Q1$CITIZENSHIP", "Q30")
                    ),
                ],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        # Verify all statements created
        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        statements = (
            db_session.query(Statement)
            .filter(Statement.politician_id == politician.id)
            .all()
        )

        assert {statement.property_id for statement in statements} == {
            "P569",
            "P570",
            "P39",
            "P19",
            "P27",
        }

    def test_reimport_updates_document(self, db_session, sample_country):
        """Test that re-importing the same statement replaces its document."""
        first_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [
                    action_api_statement_to_rest(
                        _item_claim("P27", "Q1$CITIZENSHIP", "Q30")
                    )
                ],
                "wikipedia_links": [],
            }
        ]
        _insert_politicians_batch(first_politicians, db_session)

        # Re-import with an updated document: same statement id, new rank
        # and an added qualifier
        updated_claim = _item_claim(
            "P27",
            "Q1$CITIZENSHIP",
            "Q30",
            qualifiers={"P580": [_time_snak("P580", "+1970-01-01T00:00:00Z")]},
        )
        updated_claim["rank"] = "preferred"

        updated_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [action_api_statement_to_rest(updated_claim)],
                "wikipedia_links": [],
            }
        ]
        _insert_politicians_batch(updated_politicians, db_session)

        # The statement document is replaced, no duplicate row
        statements = db_session.query(Statement).all()
        assert len(statements) == 1
        statement = statements[0]
        assert statement.wikidata_statement_id == "Q1$CITIZENSHIP"
        assert statement.property_id == "P27"
        assert statement.entity_id == "Q30"
        assert statement.document["rank"] == "preferred"
        assert statement.document["qualifiers"] == [
            {
                "property": {"id": "P580", "data_type": "time"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+1970-01-01T00:00:00Z",
                        "precision": 11,
                        "calendarmodel": _CALENDAR_MODEL,
                    },
                },
            }
        ]

    def test_statement_metadata_preserved(self, db_session):
        """Test that rank, qualifiers, and references are kept in the document."""
        claim = _item_claim("P39", "Q1$TEST_STATEMENT", "Q30185")
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.flush()

        claim["references"] = [
            {
                "hash": "4" * 40,
                "snaks": {
                    "P854": [
                        {
                            "snaktype": "value",
                            "property": "P854",
                            "datatype": "url",
                            "datavalue": {
                                "value": "https://example.org/source",
                                "type": "string",
                            },
                        }
                    ]
                },
                "snaks-order": ["P854"],
            }
        ]

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [action_api_statement_to_rest(claim)],
                "wikipedia_links": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        statement = db_session.query(Statement).first()
        assert statement.wikidata_statement_id == "Q1$TEST_STATEMENT"
        assert statement.document["rank"] == "normal"
        assert statement.document["references"] == [
            {
                "hash": "4" * 40,
                "parts": [
                    {
                        "property": {"id": "P854", "data_type": "url"},
                        "value": {
                            "type": "value",
                            "content": "https://example.org/source",
                        },
                    }
                ],
            }
        ]

    def test_insert_politicians_batch_with_wikipedia_links(
        self,
        db_session,
        sample_wikipedia_project,
        sample_french_wikipedia_project,
    ):
        """Test inserting politicians with Wikipedia links."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "statements": [],
                "wikipedia_links": [
                    {
                        "url": "https://en.wikipedia.org/wiki/John_Doe",
                        "wikipedia_project_id": sample_wikipedia_project.wikidata_id,
                    },
                    {
                        "url": "https://fr.wikipedia.org/wiki/John_Doe",
                        "wikipedia_project_id": sample_french_wikipedia_project.wikidata_id,
                    },
                ],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

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
        wiki_projects = {w.wikipedia_project_id for w in wiki_links}
        assert wiki_projects == {
            sample_wikipedia_project.wikidata_id,
            sample_french_wikipedia_project.wikidata_id,
        }


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

"""Tests for WikidataPoliticianImporter."""

from datetime import datetime, timezone
from poliloom.models import (
    ArchivedPage,
    Country,
    Language,
    Politician,
    Position,
    Location,
    Property,
    PropertyType,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)
from poliloom.importer.politician import (
    _insert_politicians_batch,
    _is_politician,
    _should_import_politician,
)
from poliloom.wikidata_entity_processor import WikidataEntityProcessor
from poliloom.wikidata_date import WikidataDate


class TestWikidataPoliticianImporter:
    """Test politician importing functionality."""

    def test_insert_politicians_batch_basic(self, db_session):
        """Test inserting a batch of politicians with basic data."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "wikipedia_sources": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "properties": [],
                "wikipedia_sources": [],
            },
        ]

        _insert_politicians_batch(politicians, db_session)

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        updated_politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe Updated",
                "properties": [],
                "wikipedia_sources": [],
            }
        ]
        _insert_politicians_batch(updated_politicians, db_session)

        final_politicians = db_session.query(Politician).all()
        assert len(final_politicians) == 1
        assert final_politicians[0].wikidata_id == "Q1"
        assert final_politicians[0].name == "John Doe Updated"

    def test_insert_politicians_batch_empty(self, db_session):
        """Test inserting empty batch of politicians."""
        politicians = []

        _insert_politicians_batch(politicians, db_session)

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

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
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.flush()

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

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
        assert "P580" in prop.qualifiers_json
        assert "P582" in prop.qualifiers_json

    def test_import_birthplace(self, db_session):
        """Test importing birthplace from Wikidata claim."""
        Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.flush()

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

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
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

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
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.flush()

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        all_props = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )

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
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        prop = db_session.query(Property).first()
        assert prop.statement_id == "Q1$TEST_STATEMENT"
        assert prop.qualifiers_json == expected_qualifiers
        assert prop.references_json == expected_references

    def test_insert_politicians_batch_with_wikipedia_sources(self, db_session):
        """Test inserting politicians with Wikipedia sources."""
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        french = Language.create_with_entity(db_session, "Q150", "French")
        french.iso_639_1 = "fr"
        french.iso_639_2 = "fra"
        en_wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wp.official_website = "https://en.wikipedia.org"
        fr_wp = WikipediaProject.create_with_entity(
            db_session, "Q8447", "French Wikipedia"
        )
        fr_wp.official_website = "https://fr.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=french.wikidata_id,
                child_entity_id=fr_wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q8447$test-statement",
            )
        )
        db_session.flush()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "wikipedia_sources": [
                    {
                        "url": "https://en.wikipedia.org/wiki/John_Doe",
                        "wikipedia_project_id": en_wp.wikidata_id,
                    },
                    {
                        "url": "https://fr.wikipedia.org/wiki/John_Doe",
                        "wikipedia_project_id": fr_wp.wikidata_id,
                    },
                ],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        politician = (
            db_session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
        )
        assert politician is not None

        wiki_sources = (
            db_session.query(WikipediaSource)
            .filter(WikipediaSource.politician_id == politician.id)
            .all()
        )
        assert len(wiki_sources) == 2
        wiki_projects = {w.wikipedia_project_id for w in wiki_sources}
        assert wiki_projects == {en_wp.wikidata_id, fr_wp.wikidata_id}


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
                            "datavalue": {"value": {"id": "Q82955"}},
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
                            "datavalue": {"value": {"id": "Q40348"}},
                        },
                    }
                ],
                "P39": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q30185"}},
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

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
                            "datavalue": {"value": {"id": "Q43229"}},
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q82955"}},
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
                            "datavalue": {"value": {"id": "Q5"}},
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q40348"}},
                        },
                    }
                ],
                "P39": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q99999"}},
                        },
                    }
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

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
                            "datavalue": {"value": {"id": "Q5"}},
                        },
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {},
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q82955"}},
                        },
                    },
                ],
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        relevant_positions = frozenset(["Q30185"])

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
                            "datavalue": {"value": {"id": "Q5"}},
                        },
                    }
                ],
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
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "-0044-03-15T00:00:00Z",
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
                                    "time": "invalid-date",
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


class TestImportSoftDeletesExtracted:
    """Test that import soft-deletes matching extracted properties."""

    def test_import_soft_deletes_matching_birth_date(self, db_session):
        """Test importing birth date soft-deletes matching extracted birth date."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1950-05-15T00:00:00Z",
                        "value_precision": 11,
                        "statement_id": "Q1$BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is not None

        imported = (
            db_session.query(Property).filter_by(statement_id="Q1$BIRTH_DATE").first()
        )
        assert imported is not None
        assert imported.deleted_at is None

    def test_import_soft_deletes_less_precise_extracted(self, db_session):
        """Test importing more precise date soft-deletes less precise extracted date."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-00-00T00:00:00Z",
            value_precision=9,
            archived_page_id=archived_page.id,
            statement_id=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1950-05-15T00:00:00Z",
                        "value_precision": 11,
                        "statement_id": "Q1$BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is not None

    def test_import_does_not_delete_more_precise_extracted(self, db_session):
        """Test importing less precise date does NOT soft-delete more precise extracted date."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1950-00-00T00:00:00Z",
                        "value_precision": 9,
                        "statement_id": "Q1$BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is None

    def test_import_soft_deletes_matching_position(self, db_session):
        """Test importing position soft-deletes matching extracted position."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            statement_id=None,
            qualifiers_json=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.POSITION,
                        "entity_id": position.wikidata_id,
                        "statement_id": "Q1$POSITION",
                        "qualifiers_json": {
                            "P580": [
                                {
                                    "datavalue": {
                                        "value": {
                                            "time": "+2020-01-01T00:00:00Z",
                                            "precision": 11,
                                        }
                                    }
                                }
                            ]
                        },
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is not None

    def test_import_soft_deletes_matching_birthplace(self, db_session):
        """Test importing birthplace soft-deletes matching extracted birthplace."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
            statement_id=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTHPLACE,
                        "entity_id": location.wikidata_id,
                        "statement_id": "Q1$BIRTHPLACE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is not None

    def test_import_does_not_delete_different_value(self, db_session):
        """Test importing different date does NOT soft-delete extracted date."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id=None,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1951-05-15T00:00:00Z",
                        "value_precision": 11,
                        "statement_id": "Q1$BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at is None

    def test_import_does_not_delete_already_deleted(self, db_session):
        """Test import does not affect already soft-deleted properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        original_deleted_at = datetime(2020, 1, 1, 12, 0, 0)
        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id=None,
            deleted_at=original_deleted_at,
        )
        db_session.add(extracted_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1950-05-15T00:00:00Z",
                        "value_precision": 11,
                        "statement_id": "Q1$BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(extracted_property)
        assert extracted_property.deleted_at == original_deleted_at

    def test_import_does_not_delete_wikidata_properties(self, db_session):
        """Test import does not soft-delete properties that came from Wikidata."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        wikidata_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=None,
            statement_id="Q1$OLD_BIRTH_DATE",
        )
        db_session.add(wikidata_property)
        db_session.flush()

        politicians = [
            {
                "wikidata_id": politician.wikidata_id,
                "name": politician.name,
                "properties": [
                    {
                        "type": PropertyType.BIRTH_DATE,
                        "value": "+1950-05-15T00:00:00Z",
                        "value_precision": 11,
                        "statement_id": "Q1$NEW_BIRTH_DATE",
                        "qualifiers_json": None,
                        "references_json": None,
                    }
                ],
                "wikipedia_sources": [],
            }
        ]

        _insert_politicians_batch(politicians, db_session)

        db_session.refresh(wikidata_property)
        assert wikidata_property.deleted_at is None

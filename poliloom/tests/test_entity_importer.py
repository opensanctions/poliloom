"""Tests for WikidataEntityImporter."""

import json
import tempfile
import os
from unittest.mock import patch

from poliloom.models import (
    WikidataEntity,
    WikidataRelation,
    Position,
    Location,
    Country,
    Language,
    WikipediaProject,
)
from poliloom.importer.entity import (
    import_entities,
    _insert_entities_batch,
    EntityCollection,
)
from poliloom.database import get_engine
from sqlalchemy.dialects.postgresql import insert


class TestWikidataEntityImporter:
    """Test entity importing functionality."""

    def test_import_entities_integration(self, db_session):
        """Test complete entity extraction workflow integration."""

        # First, set up hierarchy in database using current approach
        hierarchy_data = [
            # Position hierarchy: Q294414 (position) -> Q4164871 (office)
            {"wikidata_id": "Q294414", "name": "position"},  # Root position class
            {
                "wikidata_id": "Q4164871",
                "name": "office",
            },  # Office (subclass of position)
            # Location hierarchy: Use actual location root from HIERARCHY_CONFIG
            {
                "wikidata_id": "Q486972",
                "name": "human settlement",
            },  # Root location class (from actual config)
            {"wikidata_id": "Q515", "name": "city"},  # City (subclass of location)
            # Country classes referenced by test entities
            {"wikidata_id": "Q6256", "name": "country"},  # Country
            {"wikidata_id": "Q5", "name": "human"},  # Human
            {"wikidata_id": "Q82955", "name": "politician"},  # Politician
            # Wikipedia project class
            {
                "wikidata_id": "Q10876391",
                "name": "Wikipedia language edition",
            },  # Wikipedia language edition
        ]

        hierarchy_relations = [
            {
                "parent_entity_id": "Q294414",
                "child_entity_id": "Q4164871",
                "statement_id": "Q4164871$test-statement-1",
            },
            {
                "parent_entity_id": "Q486972",
                "child_entity_id": "Q515",
                "statement_id": "Q515$test-statement-1",
            },
        ]

        # Insert hierarchy data first
        stmt = insert(WikidataEntity).values(hierarchy_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(hierarchy_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
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
            # Wikipedia project entity - should be extracted
            {
                "id": "Q328",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "English Wikipedia"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q10876391"},
                                    "type": "wikibase-entityid",
                                },  # Wikipedia language edition
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P424": [
                        {  # Wikimedia language code
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P424",
                                "datavalue": {"value": "en", "type": "string"},
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P856": [
                        {  # official website
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P856",
                                "datavalue": {
                                    "value": "https://en.wikipedia.org/",
                                    "type": "string",
                                },
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
            # Clear existing entity data
            db_session.query(Position).delete()
            db_session.query(Location).delete()
            db_session.query(Country).delete()
            db_session.query(WikipediaProject).delete()
            db_session.commit()

            # Test extraction
            with patch("poliloom.dump_reader.calculate_file_chunks") as mock_chunks:
                # Mock chunks to return single chunk for simpler testing
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]

                import_entities(temp_file_path, batch_size=10)

            # Verify entities were actually saved to database
            positions = db_session.query(Position).all()
            locations = db_session.query(Location).all()
            countries = db_session.query(Country).all()
            wikipedia_projects = db_session.query(WikipediaProject).all()

            assert len(positions) == 1
            assert len(locations) == 1
            assert len(countries) == 1
            assert len(wikipedia_projects) == 1

            # Verify specific entity data
            position = positions[0]
            assert position.wikidata_id == "Q123456"
            assert position.wikidata_entity.name == "Test Office Position"

            location = locations[0]
            assert location.wikidata_id == "Q789012"
            assert location.wikidata_entity.name == "Test City Location"

            country = countries[0]
            assert country.wikidata_id == "Q345678"
            assert country.name == "Test Country"
            assert country.iso_code == "TC"

            wikipedia_project = wikipedia_projects[0]
            assert wikipedia_project.wikidata_id == "Q328"
            assert wikipedia_project.name == "English Wikipedia"
            assert wikipedia_project.official_website == "https://en.wikipedia.org/"

        finally:
            os.unlink(temp_file_path)

    def test_insert_positions_batch(self, db_session):
        """Test inserting a batch of positions."""
        positions = [
            {
                "wikidata_id": "Q1",
                "name": "Position 1",
                "description": "First position",
            },
            {
                "wikidata_id": "Q2",
                "name": "Position 2",
                "description": "Second position",
            },
        ]

        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in positions:
            collection.add_entity(pos)

        _insert_entities_batch(collection, get_engine())

        # Verify positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 2
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_positions_batch_with_duplicates(self, db_session):
        """Test inserting positions with some duplicates."""
        # Insert initial batch
        initial_positions = [
            {
                "wikidata_id": "Q1",
                "name": "Position 1",
                "description": "First position",
            },
            {
                "wikidata_id": "Q2",
                "name": "Position 2",
                "description": "Second position",
            },
        ]
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in initial_positions:
            collection.add_entity(pos)
        _insert_entities_batch(collection, get_engine())

        # Insert batch with some duplicates and new items
        positions_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "name": "Position 1 Updated",
                "description": "First position updated",
            },  # Duplicate (should update)
            {
                "wikidata_id": "Q2",
                "name": "Position 2",
                "description": "Second position",
            },  # Duplicate (no change)
            {
                "wikidata_id": "Q3",
                "name": "Position 3",
                "description": "Third position",
            },  # New
        ]
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in positions_with_duplicates:
            collection.add_entity(pos)
        _insert_entities_batch(collection, get_engine())

        # Verify all positions exist with correct data
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 3
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Verify Q1 was updated
        q1_position = (
            db_session.query(Position).filter(Position.wikidata_id == "Q1").first()
        )
        assert q1_position.wikidata_entity.name == "Position 1 Updated"

    def test_insert_positions_batch_empty(self, db_session):
        """Test inserting empty batch of positions."""
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        _insert_entities_batch(collection, get_engine())

        # Verify no positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, db_session):
        """Test inserting a batch of locations."""
        locations = [
            {
                "wikidata_id": "Q1",
                "name": "Location 1",
                "description": "First location",
            },
            {
                "wikidata_id": "Q2",
                "name": "Location 2",
                "description": "Second location",
            },
        ]

        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations:
            collection.add_entity(loc)

        _insert_entities_batch(collection, get_engine())

        # Verify locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 2
        wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_locations_batch_with_duplicates(self, db_session):
        """Test inserting locations with some duplicates."""
        locations = [
            {
                "wikidata_id": "Q1",
                "name": "Location 1",
                "description": "First location",
            },
            {
                "wikidata_id": "Q2",
                "name": "Location 2",
                "description": "Second location",
            },
            {
                "wikidata_id": "Q3",
                "name": "Location 3",
                "description": "Third location",
            },
        ]

        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations:
            collection.add_entity(loc)
        _insert_entities_batch(collection, get_engine())

        # Insert again with some duplicates - should handle gracefully
        locations_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "name": "Location 1 Updated",
                "description": "First location updated",
            },  # Duplicate
            {
                "wikidata_id": "Q4",
                "name": "Location 4",
                "description": "Fourth location",
            },  # New
        ]
        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations_with_duplicates:
            collection.add_entity(loc)
        _insert_entities_batch(collection, get_engine())

        # Should now have 4 total locations
        all_locations = db_session.query(Location).all()
        assert len(all_locations) == 4
        wikidata_ids = {loc.wikidata_id for loc in all_locations}
        assert wikidata_ids == {"Q1", "Q2", "Q3", "Q4"}

    def test_insert_locations_batch_empty(self, db_session):
        """Test inserting empty batch of locations."""
        collection = EntityCollection(model_class=Location, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        _insert_entities_batch(collection, get_engine())

        # Verify no locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 0

    def test_insert_countries_batch(self, db_session):
        """Test inserting a batch of countries."""
        countries = [
            {
                "wikidata_id": "Q1",
                "name": "Country 1",
                "description": "First country",
                "iso_code": "C1",
            },
            {
                "wikidata_id": "Q2",
                "name": "Country 2",
                "description": "Second country",
                "iso_code": "C2",
            },
        ]

        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in countries:
            collection.add_entity(country)

        _insert_entities_batch(collection, get_engine())

        # Verify countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 2
        wikidata_ids = {country.wikidata_id for country in inserted_countries}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify specific country data
        country1 = db_session.query(Country).filter(Country.wikidata_id == "Q1").first()
        assert country1.name == "Country 1"
        assert country1.iso_code == "C1"

    def test_insert_countries_batch_empty(self, db_session):
        """Test inserting empty batch of countries."""
        collection = EntityCollection(model_class=Country, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        _insert_entities_batch(collection, get_engine())

        # Verify no countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 0

    def test_insert_countries_batch_with_duplicates_handling(self, db_session):
        """Test that countries batch uses ON CONFLICT DO UPDATE."""
        countries = [
            {
                "wikidata_id": "Q1",
                "name": "Country 1",
                "description": "First country",
                "iso_code": "C1",
            },
        ]

        # Insert first time
        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in countries:
            collection.add_entity(country)
        _insert_entities_batch(collection, get_engine())

        # Insert again with updated name - should update
        updated_countries = [
            {
                "wikidata_id": "Q1",
                "name": "Country 1 Updated",
                "description": "First country updated",
                "iso_code": "C1",
            },
        ]
        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in updated_countries:
            collection.add_entity(country)
        _insert_entities_batch(collection, get_engine())

        # Should still have only one country but with updated name
        final_countries = db_session.query(Country).all()
        assert len(final_countries) == 1
        assert final_countries[0].wikidata_id == "Q1"
        assert final_countries[0].name == "Country 1 Updated"

    def test_insert_languages_batch(self, db_session):
        """Test inserting a batch of languages."""
        languages = [
            {
                "wikidata_id": "Q1",
                "name": "English",
                "description": "English language",
                "iso1_code": "en",
                "iso3_code": "eng",
            },
            {
                "wikidata_id": "Q2",
                "name": "Spanish",
                "description": "Spanish language",
                "iso1_code": "es",
                "iso3_code": "spa",
            },
        ]

        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        _insert_entities_batch(collection, get_engine())

        # Verify languages were inserted
        inserted_languages = db_session.query(Language).all()
        assert len(inserted_languages) == 2
        wikidata_ids = {lang.wikidata_id for lang in inserted_languages}
        assert wikidata_ids == {"Q1", "Q2"}
        iso1_codes = {lang.iso1_code for lang in inserted_languages}
        iso3_codes = {lang.iso3_code for lang in inserted_languages}
        assert iso1_codes == {"en", "es"}
        assert iso3_codes == {"eng", "spa"}

    def test_insert_languages_batch_with_duplicates_handling(self, db_session):
        """Test that languages batch uses ON CONFLICT DO UPDATE."""
        languages = [
            {
                "wikidata_id": "Q1",
                "name": "English",
                "description": "English language",
                "iso1_code": "en",
                "iso3_code": "eng",
            },
        ]

        # Insert first time
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        _insert_entities_batch(collection, get_engine())

        # Insert again with updated name - should update
        updated_languages = [
            {
                "wikidata_id": "Q1",
                "name": "English Language",
                "description": "English language updated",
                "iso1_code": "en",
                "iso3_code": "eng",
            },
        ]
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in updated_languages:
            collection.add_entity(lang)
        _insert_entities_batch(collection, get_engine())

        # Should still have only one language but with updated name
        final_languages = db_session.query(Language).all()
        assert len(final_languages) == 1
        assert final_languages[0].wikidata_id == "Q1"
        assert final_languages[0].name == "English Language"
        assert final_languages[0].iso1_code == "en"

    def test_insert_languages_batch_empty(self, db_session):
        """Test inserting empty batch of languages."""
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        _insert_entities_batch(collection, get_engine())

        # Verify no languages were inserted
        inserted_languages = db_session.query(Language).all()
        assert len(inserted_languages) == 0

    def test_insert_wikipedia_projects_batch(self, db_session):
        """Test inserting a batch of Wikipedia projects."""
        # Create a language for linking
        lang = Language.create_with_entity(db_session, "Q1860", "English")
        lang.iso1_code = "en"
        lang.iso3_code = "eng"
        db_session.commit()

        wikipedia_projects = [
            {
                "wikidata_id": "Q328",
                "name": "English Wikipedia",
                "description": "English edition of Wikipedia",
            },
            {
                "wikidata_id": "Q200183",
                "name": "Simple English Wikipedia",
                "description": "Simple English edition of Wikipedia",
            },
        ]

        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in wikipedia_projects:
            collection.add_entity(project)

        _insert_entities_batch(collection, get_engine())

        # Verify Wikipedia projects were inserted
        inserted_projects = db_session.query(WikipediaProject).all()
        assert len(inserted_projects) == 2
        wikidata_ids = {project.wikidata_id for project in inserted_projects}
        assert wikidata_ids == {"Q328", "Q200183"}

        # Verify specific project data
        project1 = (
            db_session.query(WikipediaProject)
            .filter(WikipediaProject.wikidata_id == "Q328")
            .first()
        )
        assert project1.name == "English Wikipedia"

        project2 = (
            db_session.query(WikipediaProject)
            .filter(WikipediaProject.wikidata_id == "Q200183")
            .first()
        )
        assert project2.name == "Simple English Wikipedia"

    def test_insert_wikipedia_projects_batch_with_duplicates_handling(self, db_session):
        """Test that Wikipedia projects batch uses ON CONFLICT DO NOTHING."""
        wikipedia_projects = [
            {
                "wikidata_id": "Q328",
                "name": "English Wikipedia",
                "description": "English edition of Wikipedia",
            },
        ]

        # Insert first time
        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in wikipedia_projects:
            collection.add_entity(project)
        _insert_entities_batch(collection, get_engine())

        # Insert again with same wikidata_id - should skip (do nothing)
        updated_projects = [
            {
                "wikidata_id": "Q328",
                "name": "English Wikipedia Updated",
                "description": "English edition of Wikipedia updated",
            },
        ]
        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in updated_projects:
            collection.add_entity(project)
        _insert_entities_batch(collection, get_engine())

        # Should still have only one project, but WikidataEntity name/description are updated
        final_projects = db_session.query(WikipediaProject).all()
        assert len(final_projects) == 1
        assert final_projects[0].wikidata_id == "Q328"
        # Name is updated because WikidataEntity has update columns for name/description
        assert final_projects[0].name == "English Wikipedia Updated"

    def test_insert_wikipedia_projects_batch_empty(self, db_session):
        """Test inserting empty batch of Wikipedia projects."""
        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )

        # Should handle empty batch gracefully without errors
        _insert_entities_batch(collection, get_engine())

        # Verify no Wikipedia projects were inserted
        inserted_projects = db_session.query(WikipediaProject).all()
        assert len(inserted_projects) == 0

    def test_wikipedia_project_filtering(self, db_session):
        """Test that Wikipedia projects are filtered correctly based on P856 and umbrella entities."""
        # Set up hierarchy
        hierarchy_data = [
            {"wikidata_id": "Q10876391", "name": "Wikipedia language edition"},
            {"wikidata_id": "Q210588", "name": "umbrella term"},
        ]
        stmt = insert(WikidataEntity).values(hierarchy_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        test_entities = [
            # Valid Wikipedia project with P856 - should be imported
            {
                "id": "Q877583",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Belarusian Wikipedia"}},
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q10876391"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P856": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P856",
                                "datavalue": {
                                    "value": "https://be.wikipedia.org/",
                                    "type": "string",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Wikipedia project with multiple P856 but one preferred - should be imported with preferred URL
            # Based on actual Q8937989 data from Wikidata
            {
                "id": "Q8937989",
                "type": "item",
                "labels": {
                    "en": {
                        "language": "en",
                        "value": "Belarusian Wikipedia (Taraškievica)",
                    }
                },
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q10876391"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P856": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P856",
                                "datavalue": {
                                    "value": "https://be-tarask.wikipedia.org/",
                                    "type": "string",
                                },
                                "datatype": "url",
                            },
                            "type": "statement",
                            "id": "Q8937989$EFBA9BBD-DF52-4301-98FE-D8C7819DC4FD",
                            "rank": "preferred",
                        },
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P856",
                                "datavalue": {
                                    "value": "https://be-x-old.wikipedia.org/",
                                    "type": "string",
                                },
                                "datatype": "url",
                            },
                            "type": "statement",
                            "id": "Q8937989$ace62c47-477a-ab53-88f9-23fd6d33b15e",
                            "rank": "normal",
                        },
                    ],
                },
            },
            # Umbrella entity (P31 = Q210588) - should NOT be imported
            {
                "id": "Q122311452",
                "type": "item",
                "labels": {
                    "en": {"language": "en", "value": "Belarusian Wikipedia (umbrella)"}
                },
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q210588"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P856": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P856",
                                "datavalue": {
                                    "value": "https://be.wikipedia.org/",
                                    "type": "string",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Wikipedia project without P856 - should NOT be imported
            {
                "id": "Q123456",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Wikipedia No URL"}},
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q10876391"},
                                    "type": "wikibase-entityid",
                                },
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
            # Clear existing data
            db_session.query(WikipediaProject).delete()
            db_session.commit()

            # Test extraction
            with patch("poliloom.dump_reader.calculate_file_chunks") as mock_chunks:
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]
                import_entities(temp_file_path, batch_size=10)

            # Verify only valid Wikipedia projects were imported
            wikipedia_projects = db_session.query(WikipediaProject).all()
            assert len(wikipedia_projects) == 2  # Only Q877583 and Q8937989

            # Verify specific project data
            qids = {p.wikidata_id for p in wikipedia_projects}
            assert qids == {"Q877583", "Q8937989"}

            # Verify official website URLs
            be_wiki = (
                db_session.query(WikipediaProject)
                .filter(WikipediaProject.wikidata_id == "Q877583")
                .first()
            )
            assert be_wiki.official_website == "https://be.wikipedia.org/"

            be_tarask_wiki = (
                db_session.query(WikipediaProject)
                .filter(WikipediaProject.wikidata_id == "Q8937989")
                .first()
            )
            # Should use preferred rank URL (https://be-tarask.wikipedia.org/)
            # and NOT the normal rank URL (https://be-x-old.wikipedia.org/)
            assert be_tarask_wiki.official_website == "https://be-tarask.wikipedia.org/"

        finally:
            os.unlink(temp_file_path)

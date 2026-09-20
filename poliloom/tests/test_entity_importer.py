"""Tests for WikidataEntityImporter."""

from unittest.mock import Mock

from poliloom.importer.entity import EntityCollection
from poliloom.models import (
    Country,
    Language,
    Location,
    Position,
    WikidataEntity,
    WikipediaProject,
)


class TestWikidataEntityImporter:
    """Test entity importing functionality."""

    def test_insert_positions_batch(self, db_session):
        """Test inserting a batch of positions."""
        positions = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Position 1"},
                    "descriptions": {"en": "First position"},
                    "aliases": {"en": ["Pos 1"]},
                },
            },
            {
                "wikidata_id": "Q2",
                "terms": {
                    "labels": {"en": "Position 2", "de": "Amt 2"},
                    "descriptions": {},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in positions:
            collection.add_entity(pos)

        collection.insert(db_session)

        # Verify positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 2
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify term maps were imported onto the WikidataEntity records
        q1_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q1")
            .one()
        )
        assert q1_entity.labels == {"en": "Position 1"}
        assert q1_entity.descriptions == {"en": "First position"}
        assert q1_entity.aliases == {"en": ["Pos 1"]}

        q2_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q2")
            .one()
        )
        assert q2_entity.labels == {"en": "Position 2", "de": "Amt 2"}
        assert q2_entity.descriptions == {}
        assert q2_entity.aliases == {}

    def test_insert_positions_batch_with_duplicates(self, db_session):
        """Test inserting positions with some duplicates."""
        # Insert initial batch
        initial_positions = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Position 1"},
                    "descriptions": {"en": "First position"},
                    "aliases": {"en": ["Pos 1"]},
                },
            },
            {
                "wikidata_id": "Q2",
                "terms": {
                    "labels": {"en": "Position 2"},
                    "descriptions": {"en": "Second position"},
                    "aliases": {},
                },
            },
        ]
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in initial_positions:
            collection.add_entity(pos)
        collection.insert(db_session)

        # Insert batch with some duplicates and new items
        positions_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Position 1 Updated", "de": "Amt 1"},
                    "descriptions": {"en": "First position updated"},
                    "aliases": {"de": ["Amt 1"]},
                },
            },  # Duplicate (should update)
            {
                "wikidata_id": "Q2",
                "terms": {
                    "labels": {"en": "Position 2"},
                    "descriptions": {"en": "Second position"},
                    "aliases": {},
                },
            },  # Duplicate (no change)
            {
                "wikidata_id": "Q3",
                "terms": {
                    "labels": {"en": "Position 3"},
                    "descriptions": {"en": "Third position"},
                    "aliases": {},
                },
            },  # New
        ]
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())
        for pos in positions_with_duplicates:
            collection.add_entity(pos)
        collection.insert(db_session)

        # Verify all positions exist with correct data
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 3
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Verify Q1 was updated
        q1_position = (
            db_session.query(Position).filter(Position.wikidata_id == "Q1").first()
        )
        assert q1_position.wikidata_entity.resolved_label == "Position 1 Updated"
        assert q1_position.wikidata_entity.labels == {
            "en": "Position 1 Updated",
            "de": "Amt 1",
        }
        assert q1_position.wikidata_entity.descriptions == {
            "en": "First position updated"
        }
        assert q1_position.wikidata_entity.aliases == {"de": ["Amt 1"]}

    def test_insert_positions_batch_empty(self, db_session):
        """Test inserting empty batch of positions."""
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        collection.insert(db_session)

        # Verify no positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, db_session):
        """Test inserting a batch of locations."""
        locations = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Location 1"},
                    "descriptions": {"en": "First location"},
                    "aliases": {"en": ["Loc 1"]},
                },
            },
            {
                "wikidata_id": "Q2",
                "terms": {
                    "labels": {"en": "Location 2"},
                    "descriptions": {"en": "Second location"},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations:
            collection.add_entity(loc)

        collection.insert(db_session)

        # Verify locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 2
        wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify term maps were imported onto the WikidataEntity records
        q1_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q1")
            .one()
        )
        assert q1_entity.labels == {"en": "Location 1"}
        assert q1_entity.descriptions == {"en": "First location"}
        assert q1_entity.aliases == {"en": ["Loc 1"]}

    def test_insert_locations_batch_with_duplicates(self, db_session):
        """Test inserting locations with some duplicates."""
        locations = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Location 1"},
                    "descriptions": {"en": "First location"},
                    "aliases": {},
                },
            },
            {
                "wikidata_id": "Q2",
                "terms": {
                    "labels": {"en": "Location 2"},
                    "descriptions": {"en": "Second location"},
                    "aliases": {},
                },
            },
            {
                "wikidata_id": "Q3",
                "terms": {
                    "labels": {"en": "Location 3"},
                    "descriptions": {"en": "Third location"},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations:
            collection.add_entity(loc)
        collection.insert(db_session)

        # Insert again with some duplicates - should handle gracefully
        locations_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "terms": {
                    "labels": {"en": "Location 1 Updated"},
                    "descriptions": {"en": "First location updated"},
                    "aliases": {"en": ["Loc 1"]},
                },
            },  # Duplicate
            {
                "wikidata_id": "Q4",
                "terms": {
                    "labels": {"en": "Location 4"},
                    "descriptions": {"en": "Fourth location"},
                    "aliases": {},
                },
            },  # New
        ]
        collection = EntityCollection(model_class=Location, shared_classes=frozenset())
        for loc in locations_with_duplicates:
            collection.add_entity(loc)
        collection.insert(db_session)

        # Should now have 4 total locations
        all_locations = db_session.query(Location).all()
        assert len(all_locations) == 4
        wikidata_ids = {loc.wikidata_id for loc in all_locations}
        assert wikidata_ids == {"Q1", "Q2", "Q3", "Q4"}

        # Verify Q1 term maps were updated
        q1_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q1")
            .one()
        )
        assert q1_entity.labels == {"en": "Location 1 Updated"}
        assert q1_entity.aliases == {"en": ["Loc 1"]}

    def test_insert_countries_batch(self, db_session):
        """Test inserting a batch of countries."""
        countries = [
            {
                "wikidata_id": "Q1",
                "iso_code": "C1",
                "terms": {
                    "labels": {"en": "Country 1"},
                    "descriptions": {"en": "First country"},
                    "aliases": {"en": ["C1 land"]},
                },
            },
            {
                "wikidata_id": "Q2",
                "iso_code": "C2",
                "terms": {
                    "labels": {"en": "Country 2"},
                    "descriptions": {"en": "Second country"},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in countries:
            collection.add_entity(country)

        collection.insert(db_session)

        # Verify countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 2
        wikidata_ids = {country.wikidata_id for country in inserted_countries}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify specific country data
        country1 = db_session.query(Country).filter(Country.wikidata_id == "Q1").first()
        assert country1.wikidata_entity.resolved_label == "Country 1"
        assert country1.iso_code == "C1"
        assert country1.wikidata_entity.labels == {"en": "Country 1"}
        assert country1.wikidata_entity.descriptions == {"en": "First country"}
        assert country1.wikidata_entity.aliases == {"en": ["C1 land"]}

    def test_insert_countries_batch_with_duplicates_handling(self, db_session):
        """Test that countries batch uses ON CONFLICT DO UPDATE."""
        countries = [
            {
                "wikidata_id": "Q1",
                "iso_code": "C1",
                "terms": {
                    "labels": {"en": "Country 1"},
                    "descriptions": {"en": "First country"},
                    "aliases": {},
                },
            },
        ]

        # Insert first time
        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in countries:
            collection.add_entity(country)
        collection.insert(db_session)

        # Insert again with updated name - should update
        updated_countries = [
            {
                "wikidata_id": "Q1",
                "iso_code": "C1",
                "terms": {
                    "labels": {"en": "Country 1 Updated"},
                    "descriptions": {"en": "First country updated"},
                    "aliases": {"en": ["C1"]},
                },
            },
        ]
        collection = EntityCollection(model_class=Country, shared_classes=frozenset())
        for country in updated_countries:
            collection.add_entity(country)
        collection.insert(db_session)

        # Should still have only one country but with updated data
        final_countries = db_session.query(Country).all()
        assert len(final_countries) == 1
        assert final_countries[0].wikidata_id == "Q1"
        assert final_countries[0].wikidata_entity.resolved_label == "Country 1 Updated"
        assert final_countries[0].wikidata_entity.labels == {"en": "Country 1 Updated"}
        assert final_countries[0].wikidata_entity.aliases == {"en": ["C1"]}

    def test_insert_languages_batch(self, db_session):
        """Test inserting a batch of languages."""
        languages = [
            {
                "wikidata_id": "Q1",
                "iso_639_1": "en",
                "iso_639_2": "eng",
                "terms": {
                    "labels": {"en": "English"},
                    "descriptions": {"en": "English language"},
                    "aliases": {"en": ["Anglish"]},
                },
            },
            {
                "wikidata_id": "Q2",
                "iso_639_1": "es",
                "iso_639_2": "spa",
                "terms": {
                    "labels": {"en": "Spanish", "es": "español"},
                    "descriptions": {"en": "Spanish language"},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        collection.insert(db_session)

        # Verify languages were inserted
        inserted_languages = db_session.query(Language).all()
        assert len(inserted_languages) == 2
        wikidata_ids = {lang.wikidata_id for lang in inserted_languages}
        assert wikidata_ids == {"Q1", "Q2"}
        iso_639_1s = {lang.iso_639_1 for lang in inserted_languages}
        iso_639_2s = {lang.iso_639_2 for lang in inserted_languages}
        assert iso_639_1s == {"en", "es"}
        assert iso_639_2s == {"eng", "spa"}

        # Verify term maps were imported onto the WikidataEntity records
        q2_entity = (
            db_session.query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id == "Q2")
            .one()
        )
        assert q2_entity.labels == {"en": "Spanish", "es": "español"}
        assert q2_entity.descriptions == {"en": "Spanish language"}
        assert q2_entity.aliases == {}

    def test_insert_languages_batch_with_duplicates_handling(self, db_session):
        """Test that languages batch uses ON CONFLICT DO UPDATE."""
        languages = [
            {
                "wikidata_id": "Q1",
                "iso_639_1": "en",
                "iso_639_2": "eng",
                "terms": {
                    "labels": {"en": "English"},
                    "descriptions": {"en": "English language"},
                    "aliases": {},
                },
            },
        ]

        # Insert first time
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        collection.insert(db_session)

        # Insert again with updated name - should update
        updated_languages = [
            {
                "wikidata_id": "Q1",
                "iso_639_1": "en",
                "iso_639_2": "eng",
                "terms": {
                    "labels": {"en": "English Language"},
                    "descriptions": {"en": "English language updated"},
                    "aliases": {"en": ["Anglish"]},
                },
            },
        ]
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in updated_languages:
            collection.add_entity(lang)
        collection.insert(db_session)

        # Should still have only one language but with updated data
        final_languages = db_session.query(Language).all()
        assert len(final_languages) == 1
        assert final_languages[0].wikidata_id == "Q1"
        assert final_languages[0].wikidata_entity.resolved_label == "English Language"
        assert final_languages[0].iso_639_1 == "en"
        assert final_languages[0].wikidata_entity.labels == {"en": "English Language"}
        assert final_languages[0].wikidata_entity.aliases == {"en": ["Anglish"]}

    def test_insert_wikipedia_projects_batch(self, db_session, sample_language):
        """Test inserting a batch of Wikipedia projects."""

        wikipedia_projects = [
            {
                "wikidata_id": "Q328",
                "terms": {
                    "labels": {"en": "English Wikipedia"},
                    "descriptions": {"en": "English edition of Wikipedia"},
                    "aliases": {"en": ["enwiki"]},
                },
            },
            {
                "wikidata_id": "Q200183",
                "terms": {
                    "labels": {"en": "Simple English Wikipedia"},
                    "descriptions": {"en": "Simple English edition of Wikipedia"},
                    "aliases": {},
                },
            },
        ]

        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in wikipedia_projects:
            collection.add_entity(project)

        collection.insert(db_session)

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
        assert project1.wikidata_entity.resolved_label == "English Wikipedia"
        assert project1.wikidata_entity.labels == {"en": "English Wikipedia"}
        assert project1.wikidata_entity.aliases == {"en": ["enwiki"]}

        project2 = (
            db_session.query(WikipediaProject)
            .filter(WikipediaProject.wikidata_id == "Q200183")
            .first()
        )
        assert project2.wikidata_entity.resolved_label == "Simple English Wikipedia"

    def test_insert_wikipedia_projects_batch_with_duplicates_handling(self, db_session):
        """Test that Wikipedia projects batch uses ON CONFLICT DO NOTHING."""
        wikipedia_projects = [
            {
                "wikidata_id": "Q328",
                "terms": {
                    "labels": {"en": "English Wikipedia"},
                    "descriptions": {"en": "English edition of Wikipedia"},
                    "aliases": {},
                },
            },
        ]

        # Insert first time
        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in wikipedia_projects:
            collection.add_entity(project)
        collection.insert(db_session)

        # Insert again with same wikidata_id - should skip (do nothing)
        updated_projects = [
            {
                "wikidata_id": "Q328",
                "terms": {
                    "labels": {"en": "English Wikipedia Updated"},
                    "descriptions": {"en": "English edition of Wikipedia updated"},
                    "aliases": {"en": ["enwiki"]},
                },
            },
        ]
        collection = EntityCollection(
            model_class=WikipediaProject, shared_classes=frozenset()
        )
        for project in updated_projects:
            collection.add_entity(project)
        collection.insert(db_session)

        # Should still have only one project, but WikidataEntity data is updated
        final_projects = db_session.query(WikipediaProject).all()
        assert len(final_projects) == 1
        assert final_projects[0].wikidata_id == "Q328"
        # Terms are updated because WikidataEntity has update columns
        assert (
            final_projects[0].wikidata_entity.resolved_label
            == "English Wikipedia Updated"
        )
        assert final_projects[0].wikidata_entity.labels == {
            "en": "English Wikipedia Updated"
        }
        assert final_projects[0].wikidata_entity.aliases == {"en": ["enwiki"]}


class TestWikipediaProjectFiltering:
    """Test Wikipedia project filtering logic in should_import method."""

    def test_valid_wikipedia_project_with_website(self):
        """Test that valid Wikipedia project with wikipedia.org URL is imported."""
        mock_entity = Mock()
        mock_entity.get_truthy_claims.return_value = [
            {"mainsnak": {"datavalue": {"value": "https://be.wikipedia.org/"}}}
        ]

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q10876391"},  # Wikipedia language edition
            subclass_ids=set(),
        )

        assert result is not None
        assert result["official_website"] == "https://be.wikipedia.org/"

    def test_wikipedia_project_with_preferred_rank_url(self):
        """Test that preferred rank URL is selected when multiple P856 exist."""
        mock_entity = Mock()
        # Truthy claims already filters to preferred, so we get preferred first
        mock_entity.get_truthy_claims.return_value = [
            {"mainsnak": {"datavalue": {"value": "https://be-tarask.wikipedia.org/"}}},
            {"mainsnak": {"datavalue": {"value": "https://be-x-old.wikipedia.org/"}}},
        ]

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q10876391"},
            subclass_ids=set(),
        )

        assert result is not None
        assert result["official_website"] == "https://be-tarask.wikipedia.org/"

    def test_umbrella_entity_not_imported(self):
        """Test that umbrella entities (Q210588) are not imported."""
        mock_entity = Mock()
        mock_entity.get_truthy_claims.return_value = [
            {"mainsnak": {"datavalue": {"value": "https://be.wikipedia.org/"}}}
        ]

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q210588"},  # umbrella term
            subclass_ids=set(),
        )

        assert result is None

    def test_wikipedia_project_without_website_not_imported(self):
        """Test that Wikipedia project without P856 is not imported."""
        mock_entity = Mock()
        mock_entity.get_truthy_claims.return_value = []  # No P856

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q10876391"},
            subclass_ids=set(),
        )

        assert result is None

    def test_wikipedia_project_with_non_wikipedia_url_not_imported(self):
        """Test that projects with non-wikipedia.org URLs are not imported."""
        mock_entity = Mock()
        mock_entity.get_truthy_claims.return_value = [
            {"mainsnak": {"datavalue": {"value": "https://example.com/"}}}
        ]

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q10876391"},
            subclass_ids=set(),
        )

        assert result is None

    def test_wikipedia_project_with_malformed_claim(self):
        """Test that malformed P856 claims are handled gracefully."""
        mock_entity = Mock()
        mock_entity.get_truthy_claims.return_value = [
            {
                "mainsnak": {}  # Missing datavalue
            }
        ]

        result = WikipediaProject.should_import(
            mock_entity,
            instance_ids={"Q10876391"},
            subclass_ids=set(),
        )

        assert result is None

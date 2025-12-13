"""Tests for WikidataEntityImporter."""

from unittest.mock import Mock

from poliloom.models import (
    Position,
    Location,
    Country,
    Language,
    WikipediaProject,
)
from poliloom.importer.entity import EntityCollection


class TestWikidataEntityImporter:
    """Test entity importing functionality."""

    def test_insert_positions_batch(self, db_session, mock_search_service):
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

        collection.insert(db_session, mock_search_service)

        # Verify positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 2
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_positions_batch_with_duplicates(
        self, db_session, mock_search_service
    ):
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
        collection.insert(db_session, mock_search_service)

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
        collection.insert(db_session, mock_search_service)

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

    def test_insert_positions_batch_empty(self, db_session, mock_search_service):
        """Test inserting empty batch of positions."""
        collection = EntityCollection(model_class=Position, shared_classes=frozenset())

        # Should handle empty batch gracefully without errors
        collection.insert(db_session, mock_search_service)

        # Verify no positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, db_session, mock_search_service):
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

        collection.insert(db_session, mock_search_service)

        # Verify locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 2
        wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_locations_batch_with_duplicates(
        self, db_session, mock_search_service
    ):
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
        collection.insert(db_session, mock_search_service)

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
        collection.insert(db_session, mock_search_service)

        # Should now have 4 total locations
        all_locations = db_session.query(Location).all()
        assert len(all_locations) == 4
        wikidata_ids = {loc.wikidata_id for loc in all_locations}
        assert wikidata_ids == {"Q1", "Q2", "Q3", "Q4"}

    def test_insert_countries_batch(self, db_session, mock_search_service):
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

        collection.insert(db_session, mock_search_service)

        # Verify countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 2
        wikidata_ids = {country.wikidata_id for country in inserted_countries}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify specific country data
        country1 = db_session.query(Country).filter(Country.wikidata_id == "Q1").first()
        assert country1.name == "Country 1"
        assert country1.iso_code == "C1"

    def test_insert_countries_batch_with_duplicates_handling(
        self, db_session, mock_search_service
    ):
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
        collection.insert(db_session, mock_search_service)

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
        collection.insert(db_session, mock_search_service)

        # Should still have only one country but with updated name
        final_countries = db_session.query(Country).all()
        assert len(final_countries) == 1
        assert final_countries[0].wikidata_id == "Q1"
        assert final_countries[0].name == "Country 1 Updated"

    def test_insert_languages_batch(self, db_session, mock_search_service):
        """Test inserting a batch of languages."""
        languages = [
            {
                "wikidata_id": "Q1",
                "name": "English",
                "description": "English language",
                "iso_639_1": "en",
                "iso_639_2": "eng",
            },
            {
                "wikidata_id": "Q2",
                "name": "Spanish",
                "description": "Spanish language",
                "iso_639_1": "es",
                "iso_639_2": "spa",
            },
        ]

        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        collection.insert(db_session, mock_search_service)

        # Verify languages were inserted
        inserted_languages = db_session.query(Language).all()
        assert len(inserted_languages) == 2
        wikidata_ids = {lang.wikidata_id for lang in inserted_languages}
        assert wikidata_ids == {"Q1", "Q2"}
        iso_639_1s = {lang.iso_639_1 for lang in inserted_languages}
        iso_639_2s = {lang.iso_639_2 for lang in inserted_languages}
        assert iso_639_1s == {"en", "es"}
        assert iso_639_2s == {"eng", "spa"}

    def test_insert_languages_batch_with_duplicates_handling(
        self, db_session, mock_search_service
    ):
        """Test that languages batch uses ON CONFLICT DO UPDATE."""
        languages = [
            {
                "wikidata_id": "Q1",
                "name": "English",
                "description": "English language",
                "iso_639_1": "en",
                "iso_639_2": "eng",
            },
        ]

        # Insert first time
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in languages:
            collection.add_entity(lang)
        collection.insert(db_session, mock_search_service)

        # Insert again with updated name - should update
        updated_languages = [
            {
                "wikidata_id": "Q1",
                "name": "English Language",
                "description": "English language updated",
                "iso_639_1": "en",
                "iso_639_2": "eng",
            },
        ]
        collection = EntityCollection(model_class=Language, shared_classes=frozenset())
        for lang in updated_languages:
            collection.add_entity(lang)
        collection.insert(db_session, mock_search_service)

        # Should still have only one language but with updated name
        final_languages = db_session.query(Language).all()
        assert len(final_languages) == 1
        assert final_languages[0].wikidata_id == "Q1"
        assert final_languages[0].name == "English Language"
        assert final_languages[0].iso_639_1 == "en"

    def test_insert_wikipedia_projects_batch(
        self, db_session, sample_language, mock_search_service
    ):
        """Test inserting a batch of Wikipedia projects."""

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

        collection.insert(db_session, mock_search_service)

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

    def test_insert_wikipedia_projects_batch_with_duplicates_handling(
        self, db_session, mock_search_service
    ):
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
        collection.insert(db_session, mock_search_service)

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
        collection.insert(db_session, mock_search_service)

        # Should still have only one project, but WikidataEntity name/description are updated
        final_projects = db_session.query(WikipediaProject).all()
        assert len(final_projects) == 1
        assert final_projects[0].wikidata_id == "Q328"
        # Name is updated because WikidataEntity has update columns for name/description
        assert final_projects[0].name == "English Wikipedia Updated"


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

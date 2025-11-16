"""Tests for supporting entity models: Country, Language, Location, Position."""

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError

from poliloom.models import Country, Language, Location, Position, WikipediaProject

from ..conftest import assert_model_fields


class TestCountry:
    """Test cases for the Country model."""

    def test_country_creation(self, db_session):
        """Test basic country creation."""
        country = Country.create_with_entity(db_session, "Q183", "Germany")
        country.iso_code = "DE"
        db_session.commit()
        db_session.refresh(country)

        assert_model_fields(country, {"wikidata_id": "Q183", "iso_code": "DE"})
        assert country.name == "Germany"

    def test_country_optional_iso_code(self, db_session):
        """Test that iso_code is optional."""
        country = Country.create_with_entity(db_session, "Q12345", "Some Territory")
        db_session.commit()
        db_session.refresh(country)

        assert_model_fields(
            country,
            {"wikidata_id": "Q12345", "iso_code": None},
        )
        assert country.name == "Some Territory"


class TestLocation:
    """Test cases for the Location model."""

    def test_location_creation(self, db_session):
        """Test basic location creation."""
        location = Location.create_with_entity(db_session, "Q60", "New York City")
        db_session.commit()

        # Refresh with wikidata_entity loaded
        location = db_session.query(Location).filter_by(wikidata_id="Q60").first()

        assert_model_fields(location, {"wikidata_id": "Q60"})
        assert location.wikidata_entity.name == "New York City"

    def test_location_unique_wikidata_id(self, db_session):
        """Test that Wikidata ID must be unique."""
        Location.create_with_entity(db_session, "Q60001", "New York City")
        db_session.commit()

        # Try to create another location with same wikidata_id (should fail at WikidataEntity level)
        with pytest.raises(IntegrityError):
            Location.create_with_entity(db_session, "Q60001", "NYC")
            db_session.commit()

        # Clean up the session
        db_session.rollback()


class TestPosition:
    """Test cases for the Position model."""

    def test_position_creation(self, db_session):
        """Test basic position creation."""
        position = Position.create_with_entity(db_session, "Q4416090", "Senator")
        db_session.commit()

        # Refresh with wikidata_entity loaded
        position = db_session.query(Position).filter_by(wikidata_id="Q4416090").first()

        assert_model_fields(position, {"wikidata_id": "Q4416090"})
        assert position.wikidata_entity.name == "Senator"


class TestPositionVectorSimilarity:
    """Test cases for Position vector similarity search functionality."""

    def test_embedding_deterministic_for_same_text(self, generate_embedding):
        """Test that embedding generation is deterministic."""
        # Test deterministic behavior
        embedding1 = generate_embedding("Prime Minister")
        embedding2 = generate_embedding("Prime Minister")
        assert embedding1 == embedding2
        assert len(embedding1) == 384

    def test_similarity_search_functionality(
        self,
        db_session,
        generate_embedding,
    ):
        """Test similarity search functionality."""
        # Create positions with embeddings
        entities_data = [
            {"wikidata_id": "Q11696", "name": "US President"},
            {"wikidata_id": "Q889821", "name": "US Governor"},
            {"wikidata_id": "Q14212", "name": "UK Prime Minister"},
        ]

        for entity_data in entities_data:
            embedding = generate_embedding(entity_data["name"])
            position = Position.create_with_entity(
                db_session, entity_data["wikidata_id"], entity_data["name"]
            )
            position.embedding = embedding

        db_session.commit()

        # Test basic similarity search - using same session
        query_embedding = generate_embedding("Chief Executive")
        results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )
        assert len(results) <= 2
        assert all(isinstance(pos, Position) for pos in results)

        # Test limit behavior
        no_query_embedding = generate_embedding("Query")
        no_results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(0)
            .all()
        )
        assert no_results == []

        one_result = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(1)
            .all()
        )
        assert len(one_result) <= 1


class TestWikipediaProject:
    """Test cases for the WikipediaProject model."""

    def test_wikipedia_project_creation(self, db_session):
        """Test basic Wikipedia project creation."""
        project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        project.language_code = "en"
        db_session.commit()
        db_session.refresh(project)

        assert_model_fields(
            project,
            {"wikidata_id": "Q328", "language_code": "en", "language_id": None},
        )
        assert project.name == "English Wikipedia"

    def test_wikipedia_project_with_language_link(self, db_session):
        """Test Wikipedia project with linked language entity."""
        # Create a language first
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso1_code = "en"
        language.iso3_code = "eng"
        db_session.commit()

        # Create Wikipedia project linked to language
        project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        project.language_code = "en"
        project.language_id = "Q1860"
        db_session.commit()
        db_session.refresh(project)

        assert_model_fields(
            project,
            {"wikidata_id": "Q328", "language_code": "en", "language_id": "Q1860"},
        )
        assert project.language is not None
        assert project.language.wikidata_id == "Q1860"
        assert project.language.name == "English"

    def test_wikipedia_project_language_code_required(self, db_session):
        """Test that language_code is required."""
        WikipediaProject.create_with_entity(db_session, "Q328", "English Wikipedia")
        # Don't set language_code - should fail on commit (NOT NULL constraint)
        with pytest.raises(ProgrammingError):
            db_session.commit()

        db_session.rollback()

    def test_wikipedia_project_unique_language_code(self, db_session):
        """Test that language_code must be unique."""
        # Create first project
        project1 = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        project1.language_code = "en"
        db_session.commit()

        # Try to create another project with same language_code
        project2 = WikipediaProject.create_with_entity(
            db_session, "Q200183", "Simple English Wikipedia"
        )
        project2.language_code = "en"  # Same as first project

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_wikipedia_project_edge_case_simple_english(self, db_session):
        """Test edge case: Simple English Wikipedia with language_code 'simple'."""
        project = WikipediaProject.create_with_entity(
            db_session, "Q200183", "Simple English Wikipedia"
        )
        project.language_code = "simple"
        # No language_id because Simple English may not be in Language table
        db_session.commit()
        db_session.refresh(project)

        assert_model_fields(
            project,
            {"wikidata_id": "Q200183", "language_code": "simple", "language_id": None},
        )
        assert project.name == "Simple English Wikipedia"
        assert project.language is None

    def test_wikipedia_project_language_deletion_cascade(self, db_session):
        """Test that deleting a language sets language_id to NULL (ON DELETE SET NULL)."""
        # Create a language
        language = Language.create_with_entity(db_session, "Q1321", "Spanish")
        language.iso1_code = "es"
        language.iso3_code = "spa"
        db_session.commit()

        # Create Wikipedia project linked to language
        project = WikipediaProject.create_with_entity(
            db_session, "Q8449", "Spanish Wikipedia"
        )
        project.language_code = "es"
        project.language_id = "Q1321"
        db_session.commit()

        # Delete the language
        db_session.delete(language)
        db_session.commit()

        # Refresh project and verify language_id is NULL
        db_session.refresh(project)
        assert project.language_id is None
        assert project.language is None
        assert project.language_code == "es"  # language_code should remain

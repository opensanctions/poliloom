"""Tests for supporting entity models: Country, Language, Location, Position."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Country, Location, Position

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

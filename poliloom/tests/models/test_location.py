"""Tests for the Location model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Location
from poliloom.embeddings import generate_embedding
from ..conftest import assert_model_fields


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

    def test_location_find_similar(
        self,
        db_session,
    ):
        """Test location similarity search functionality."""
        # Create test locations with embeddings
        location_data = [
            ("Q60", "New York City"),
            ("Q65", "Los Angeles"),
            ("Q1297", "Chicago"),
        ]

        locations = []
        for wikidata_id, name in location_data:
            location = Location.create_with_entity(db_session, wikidata_id, name)
            location.embedding = generate_embedding(name)
            locations.append(location)

        db_session.commit()

        # Test similarity search - using same session
        query_embedding = generate_embedding("New York")
        similar = (
            db_session.query(Location)
            .filter(Location.embedding.isnot(None))
            .order_by(Location.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )

        assert len(similar) <= 2
        if len(similar) > 0:
            assert isinstance(similar[0], Location)
            assert hasattr(similar[0], "wikidata_entity")
            assert similar[0].wikidata_entity.name is not None

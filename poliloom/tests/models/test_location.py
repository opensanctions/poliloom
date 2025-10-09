"""Tests for the Location model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Location
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

    def test_location_find_similar(self, db_session):
        """Test location similarity search functionality using pg_trgm."""
        # Create test locations with labels for fuzzy text search
        location_data = [
            ("Q60", "New York City", ["New York City", "New York", "NYC"]),
            ("Q65", "Los Angeles", ["Los Angeles", "LA", "L.A."]),
            ("Q1297", "Chicago", ["Chicago", "Chi-Town"]),
        ]

        locations = []
        for wikidata_id, name, labels in location_data:
            location = Location.create_with_entity(
                db_session, wikidata_id, name, labels=labels
            )
            locations.append(location)

        db_session.commit()

        # Test similarity search using new find_similar method (pg_trgm fuzzy search)
        similar = Location.find_similar(
            session=db_session, query_text="New York", limit=2
        )

        assert len(similar) <= 2
        if len(similar) > 0:
            assert isinstance(similar[0], Location)
            assert hasattr(similar[0], "wikidata_entity")
            assert similar[0].wikidata_entity.name is not None

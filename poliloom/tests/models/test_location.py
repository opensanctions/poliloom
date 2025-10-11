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

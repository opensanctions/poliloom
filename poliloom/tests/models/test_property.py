"""Tests for the Property model."""

from poliloom.models import Politician, Property, PropertyType
from ..conftest import assert_model_fields


class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(self, db_session, sample_politician_data):
        """Test basic property creation."""
        # Create politician
        politician = Politician.create_with_entity(
            db_session,
            sample_politician_data["wikidata_id"],
            sample_politician_data["name"],
        )
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTH_DATE,
                "value": "1990-01-01",
                "archived_page_id": None,
            },
        )

    def test_property_default_values(self, db_session, sample_politician_data):
        """Test default values for property fields."""
        # Create politician
        politician = Politician.create_with_entity(
            db_session,
            sample_politician_data["wikidata_id"],
            sample_politician_data["name"],
        )
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id, type=PropertyType.BIRTH_DATE, value="1980"
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTH_DATE,
                "value": "1980",
                "archived_page_id": None,
            },
        )

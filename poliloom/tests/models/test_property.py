"""Tests for the Property model."""

from poliloom.models import Property, PropertyType
from ..conftest import assert_model_fields


class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(self, db_session, sample_politician):
        """Test basic property creation."""
        # Use fixture politician
        politician = sample_politician

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

    def test_property_default_values(self, db_session, sample_politician):
        """Test default values for property fields."""
        # Use fixture politician
        politician = sample_politician
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

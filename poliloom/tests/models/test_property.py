"""Tests for the Property model."""

from poliloom.models import Property, PropertyType
from ..conftest import assert_model_fields


class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(self, db_session, sample_politician):
        """Test basic property creation."""
        # Use fixture politician
        politician = sample_politician

        # Create property with basic required fields
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            value_precision=11,
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
                "value_precision": 11,
                "archived_page_id": None,
            },
        )

    def test_property_default_values(self, db_session, sample_politician):
        """Test default values for property fields."""
        # Use fixture politician
        politician = sample_politician
        db_session.refresh(politician)

        # Create property with minimal required data
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980",
            value_precision=9,  # Year precision
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
                "value_precision": 9,
                "qualifiers_json": None,
                "references_json": None,
                "archived_page_id": None,
            },
        )

"""Tests for the Country model."""

from poliloom.models import Country
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

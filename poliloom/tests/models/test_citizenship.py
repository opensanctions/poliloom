"""Tests for the HasCitizenship model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Politician, Country, HasCitizenship
from ..conftest import assert_model_fields


class TestHasCitizenship:
    """Test cases for the HasCitizenship model."""

    def test_has_citizenship_creation(
        self,
        db_session,
        sample_politician,
        sample_country,
    ):
        """Test basic citizenship relationship creation."""
        # Use fixture entities
        politician = sample_politician
        country = sample_country

        # Create citizenship
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship)
        db_session.commit()
        db_session.refresh(citizenship)

        assert_model_fields(
            citizenship,
            {"politician_id": politician.id, "country_id": country.wikidata_id},
        )

    def test_has_citizenship_multiple_citizenships_per_politician(
        self, db_session, sample_politician, sample_country
    ):
        """Test that a politician can have multiple citizenships."""
        # Use fixture politician and US country, create Canada country
        politician = sample_politician
        country1 = sample_country  # Q30 United States
        country2 = Country.create_with_entity(db_session, "Q16", "Canada", "CA")

        db_session.commit()
        db_session.refresh(country2)

        # Create two citizenships for the same politician
        citizenship1 = HasCitizenship(
            politician_id=politician.id, country_id=country1.wikidata_id
        )
        citizenship2 = HasCitizenship(
            politician_id=politician.id, country_id=country2.wikidata_id
        )

        db_session.add_all([citizenship1, citizenship2])
        db_session.commit()

        # Verify both citizenships exist
        citizenships = (
            db_session.query(HasCitizenship)
            .filter_by(politician_id=politician.id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        politician_refreshed = (
            db_session.query(Politician).filter_by(id=politician.id).first()
        )
        assert len(politician_refreshed.citizenships) == 2
        country_names = {c.country.name for c in politician_refreshed.citizenships}
        assert "United States" in country_names
        assert "Canada" in country_names

    def test_has_citizenship_multiple_politicians_per_country(
        self, db_session, sample_country
    ):
        """Test that a country can have multiple citizen politicians."""
        # Use fixture country and create custom politicians
        country = sample_country
        politician1 = Politician.create_with_entity(db_session, "Q111", "Alice Smith")
        politician2 = Politician.create_with_entity(db_session, "Q222", "Bob Jones")
        db_session.commit()
        db_session.refresh(politician1)
        db_session.refresh(politician2)

        # Create two citizenships for the same country
        citizenship1 = HasCitizenship(
            politician_id=politician1.id, country_id=country.wikidata_id
        )
        citizenship2 = HasCitizenship(
            politician_id=politician2.id, country_id=country.wikidata_id
        )

        db_session.add_all([citizenship1, citizenship2])
        db_session.commit()

        # Verify both citizenships exist
        citizenships = (
            db_session.query(HasCitizenship)
            .filter_by(country_id=country.wikidata_id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        country_refreshed = (
            db_session.query(Country).filter_by(wikidata_id=country.wikidata_id).first()
        )
        assert len(country_refreshed.citizens) == 2
        politician_names = {c.politician.name for c in country_refreshed.citizens}
        assert "Alice Smith" in politician_names
        assert "Bob Jones" in politician_names

    def test_has_citizenship_prevents_duplicate_relationships(
        self, db_session, sample_politician, sample_country
    ):
        """Test database constraints prevent duplicate citizenship relationships."""
        # Use fixture entities
        politician = sample_politician
        country = sample_country

        # Create first citizenship
        citizenship1 = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship1)
        db_session.commit()

        # Attempt to create duplicate
        citizenship2 = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()

        # Clean up failed transaction
        db_session.rollback()

"""Tests for the Politician model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Politician, Property, PropertyType
from ..conftest import assert_model_fields


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(self, db_session):
        """Test basic politician creation."""
        politician = Politician(name="Jane Smith", wikidata_id="Q789012")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Jane Smith", "wikidata_id": "Q789012"},
        )

    def test_politician_unique_wikidata_id(self, db_session, sample_politician_data):
        """Test that wikidata_id must be unique."""
        # Create first politician
        politician1 = Politician(**sample_politician_data)
        db_session.add(politician1)
        db_session.commit()

        # Try to create duplicate
        duplicate_politician = Politician(
            name="Different Name",
            wikidata_id=sample_politician_data["wikidata_id"],  # Same wikidata_id
        )
        db_session.add(duplicate_politician)

        with pytest.raises(IntegrityError):
            db_session.commit()

        # Roll back the failed transaction to clean up the session
        db_session.rollback()

    def test_politician_default_values(self, db_session):
        """Test default values for politician fields."""
        politician = Politician(name="Test Person")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Test Person", "is_deceased": False, "wikidata_id": None},
        )

    def test_politician_cascade_delete_properties(
        self, db_session, sample_politician_data
    ):
        """Test that deleting a politician cascades to properties."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
        )
        db_session.add(prop)
        db_session.commit()

        # Delete politician should cascade to properties
        db_session.delete(politician)
        db_session.commit()

        # Property should be deleted
        assert (
            db_session.query(Property).filter_by(politician_id=politician.id).first()
            is None
        )

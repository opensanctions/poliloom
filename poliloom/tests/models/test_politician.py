"""Tests for the Politician model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Politician, Property, PropertyType
from ..conftest import assert_model_fields


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(self, db_session):
        """Test basic politician creation."""
        politician = Politician.create_with_entity(db_session, "Q789012", "Jane Smith")
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Jane Smith", "wikidata_id": "Q789012"},
        )

    def test_politician_unique_wikidata_id(self, db_session, sample_politician_data):
        """Test that wikidata_id must be unique."""
        # Create first politician
        Politician.create_with_entity(
            db_session,
            sample_politician_data["wikidata_id"],
            sample_politician_data["name"],
        )
        db_session.commit()

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            Politician.create_with_entity(
                db_session,
                sample_politician_data["wikidata_id"],  # Same wikidata_id
                "Different Name",
            )
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

    def test_politician_cascade_delete_properties(self, db_session, sample_politician):
        """Test that deleting a politician cascades to properties."""
        # Use fixture politician
        politician = sample_politician

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

    def test_politician_with_all_property_types(
        self,
        db_session,
        sample_politician,
        sample_position,
        sample_location,
        sample_country,
    ):
        """Test politician with all property types stored correctly."""
        # Use fixture entities
        politician = sample_politician
        position = sample_position
        location = sample_location
        country = sample_country

        # Create properties of all types
        birth_date = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1970-01-15",
            value_precision=11,
        )
        death_date = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="2020-12-31",
            value_precision=11,
        )
        birthplace = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )
        pos_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datatype": "time",
                        "snaktype": "value",
                        "datavalue": {
                            "type": "time",
                            "value": {
                                "time": "+2020-01-01T00:00:00Z",
                                "precision": 9,
                            },
                        },
                    }
                ],
                "P582": [
                    {
                        "datatype": "time",
                        "snaktype": "value",
                        "datavalue": {
                            "type": "time",
                            "value": {
                                "time": "+2024-01-01T00:00:00Z",
                                "precision": 9,
                            },
                        },
                    }
                ],
            },
        )
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        db_session.add_all(
            [birth_date, death_date, birthplace, pos_property, citizenship]
        )
        db_session.commit()
        db_session.refresh(politician)

        # Verify all properties are in politician.properties
        properties = politician.properties
        assert len(properties) == 5

        # Group by type for easy verification
        properties_by_type = {prop.type: prop for prop in properties}

        # Verify each property type exists with correct type enum value
        assert PropertyType.BIRTH_DATE in properties_by_type
        assert (
            properties_by_type[PropertyType.BIRTH_DATE].type == PropertyType.BIRTH_DATE
        )
        assert properties_by_type[PropertyType.BIRTH_DATE].value == "1970-01-15"
        assert properties_by_type[PropertyType.BIRTH_DATE].entity_id is None

        assert PropertyType.DEATH_DATE in properties_by_type
        assert (
            properties_by_type[PropertyType.DEATH_DATE].type == PropertyType.DEATH_DATE
        )
        assert properties_by_type[PropertyType.DEATH_DATE].value == "2020-12-31"
        assert properties_by_type[PropertyType.DEATH_DATE].entity_id is None

        assert PropertyType.BIRTHPLACE in properties_by_type
        assert (
            properties_by_type[PropertyType.BIRTHPLACE].type == PropertyType.BIRTHPLACE
        )
        assert (
            properties_by_type[PropertyType.BIRTHPLACE].entity_id
            == location.wikidata_id
        )
        assert properties_by_type[PropertyType.BIRTHPLACE].value is None

        assert PropertyType.POSITION in properties_by_type
        assert properties_by_type[PropertyType.POSITION].type == PropertyType.POSITION
        assert (
            properties_by_type[PropertyType.POSITION].entity_id == position.wikidata_id
        )
        assert properties_by_type[PropertyType.POSITION].value is None
        assert properties_by_type[PropertyType.POSITION].qualifiers_json is not None

        assert PropertyType.CITIZENSHIP in properties_by_type
        assert (
            properties_by_type[PropertyType.CITIZENSHIP].type
            == PropertyType.CITIZENSHIP
        )
        assert (
            properties_by_type[PropertyType.CITIZENSHIP].entity_id
            == country.wikidata_id
        )
        assert properties_by_type[PropertyType.CITIZENSHIP].value is None

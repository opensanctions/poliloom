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

    def test_birthplace_property_creation(
        self, db_session, sample_politician, sample_location
    ):
        """Test creating a birthplace property with entity_id."""
        # Use fixture politician and location
        politician = sample_politician
        location = sample_location

        # Create birthplace property with entity_id
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTHPLACE,
                "entity_id": location.wikidata_id,
                "value": None,
                "value_precision": None,
                "archived_page_id": None,
            },
        )

    def test_position_property_creation(
        self, db_session, sample_politician, sample_position
    ):
        """Test creating a position property with entity_id."""
        # Use fixture politician and position
        politician = sample_politician
        position = sample_position

        # Create position property with entity_id
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.POSITION,
                "entity_id": position.wikidata_id,
                "value": None,
                "value_precision": None,
                "archived_page_id": None,
            },
        )

    def test_citizenship_property_creation(
        self, db_session, sample_politician, sample_country
    ):
        """Test creating a citizenship property with entity_id."""
        # Use fixture politician and country
        politician = sample_politician
        country = sample_country

        # Create citizenship property with entity_id
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.CITIZENSHIP,
                "entity_id": country.wikidata_id,
                "value": None,
                "value_precision": None,
                "archived_page_id": None,
            },
        )

    def test_death_date_property_creation(self, db_session, sample_politician):
        """Test creating a death date property with value."""
        # Use fixture politician
        politician = sample_politician

        # Create death date property with value
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="2020-12-31",
            value_precision=11,  # Day precision
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.DEATH_DATE,
                "value": "2020-12-31",
                "value_precision": 11,
                "entity_id": None,
                "archived_page_id": None,
            },
        )

    def test_property_type_enum_coverage(self):
        """Test that all property types are covered."""
        # Ensure all enum values are tested
        expected_types = {
            PropertyType.BIRTH_DATE,
            PropertyType.DEATH_DATE,
            PropertyType.BIRTHPLACE,
            PropertyType.POSITION,
            PropertyType.CITIZENSHIP,
        }
        assert len(expected_types) == 5
        assert PropertyType.BIRTH_DATE == "BIRTH_DATE"
        assert PropertyType.DEATH_DATE == "DEATH_DATE"
        assert PropertyType.BIRTHPLACE == "BIRTHPLACE"
        assert PropertyType.POSITION == "POSITION"
        assert PropertyType.CITIZENSHIP == "CITIZENSHIP"

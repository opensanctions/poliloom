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
        assert PropertyType.BIRTH_DATE == "P569"
        assert PropertyType.DEATH_DATE == "P570"
        assert PropertyType.BIRTHPLACE == "P19"
        assert PropertyType.POSITION == "P39"
        assert PropertyType.CITIZENSHIP == "P27"


class TestPropertyShouldStore:
    """Test cases for the Property.should_store() method."""

    def test_should_store_birth_date_no_existing(self, db_session, sample_politician):
        """Test storing birth date when no existing date exists."""
        politician = sample_politician

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birth_date_more_precise(self, db_session, sample_politician):
        """Test storing birth date when new date is more precise."""
        politician = sample_politician

        # Create existing property with year precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,  # Year precision
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store more precise date (day precision)
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,  # Day precision
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birth_date_less_precise(self, db_session, sample_politician):
        """Test not storing birth date when new date is less precise."""
        politician = sample_politician

        # Create existing property with day precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,  # Day precision
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store less precise date (year precision)
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,  # Year precision
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_birth_date_different_year(
        self, db_session, sample_politician
    ):
        """Test storing birth date when years are different."""
        politician = sample_politician

        # Create existing property for 1990
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store date for different year
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1991-01-01T00:00:00Z",
            value_precision=11,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_no_existing(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when no existing position exists."""
        politician = sample_politician
        position = sample_position

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-00-00T00:00:00Z", "precision": 9}
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_more_precise_dates(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when new dates are more precise."""
        politician = sample_politician
        position = sample_position

        # Create existing position with year precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-00-00T00:00:00Z",
                                "precision": 9,  # Year precision
                            }
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store position with more precise start date
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-01-15T00:00:00Z",
                                "precision": 11,  # Day precision
                            }
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_less_precise_dates(
        self, db_session, sample_politician, sample_position
    ):
        """Test not storing position when new dates are less precise."""
        politician = sample_politician
        position = sample_position

        # Create existing position with day precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-01-15T00:00:00Z",
                                "precision": 11,  # Day precision
                            }
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store position with less precise start date
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-00-00T00:00:00Z",
                                "precision": 9,  # Year precision
                            }
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_position_different_timeframe(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when timeframes are different."""
        politician = sample_politician
        position = sample_position

        # Create existing position for 2020
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store position for different year
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2021-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birthplace_no_existing(
        self, db_session, sample_politician, sample_location
    ):
        """Test storing birthplace when no existing birthplace exists."""
        politician = sample_politician
        location = sample_location

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birthplace_duplicate(
        self, db_session, sample_politician, sample_location
    ):
        """Test not storing birthplace when duplicate exists."""
        politician = sample_politician
        location = sample_location

        # Create existing birthplace
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store duplicate birthplace
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_citizenship_no_existing(
        self, db_session, sample_politician, sample_country
    ):
        """Test storing citizenship when no existing citizenship exists."""
        politician = sample_politician
        country = sample_country

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_citizenship_duplicate(
        self, db_session, sample_politician, sample_country
    ):
        """Test not storing citizenship when duplicate exists."""
        politician = sample_politician
        country = sample_country

        # Create existing citizenship
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store duplicate citizenship
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_position_no_dates_when_dates_exist(
        self, db_session, sample_politician, sample_position
    ):
        """Test not storing position without dates when position with dates exists."""
        politician = sample_politician
        position = sample_position

        # Create existing position with dates (May 24, 2016 - present)
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2016-05-24T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.commit()

        # Try to store same position without any dates
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json=None,  # No dates specified
        )

        assert new_property.should_store(db_session) is False

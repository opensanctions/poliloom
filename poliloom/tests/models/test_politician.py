"""Tests for the Politician model."""

from poliloom.models import (
    Politician,
    Property,
    PropertyType,
)
from poliloom.wikidata.date import WikidataDate


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_cascade_delete_properties(
        self, db_session, sample_politician, create_birth_date
    ):
        """Test that deleting a politician cascades to properties."""
        # Use fixture politician
        politician = sample_politician

        # Create property
        create_birth_date(politician)
        db_session.flush()

        # Delete politician should cascade to properties
        db_session.delete(politician)
        db_session.flush()

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
        create_birth_date,
        create_death_date,
        create_birthplace,
        create_position,
        create_citizenship,
    ):
        """Test politician with all property types stored correctly."""
        # Use fixture entities
        politician = sample_politician
        position = sample_position
        location = sample_location
        country = sample_country

        # Create properties of all types using fixtures
        qualifiers = {
            "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
        }
        create_birth_date(politician, value="1970-01-15")
        create_death_date(politician, value="2020-12-31")
        create_birthplace(politician, location)
        create_position(politician, position, qualifiers_json=qualifiers)
        create_citizenship(politician, country)
        db_session.flush()
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


class TestPoliticianQueryBase:
    """Test cases for Politician.query_base method."""

    def test_query_base_returns_non_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base returns non-soft-deleted politicians."""
        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_base_excludes_soft_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base excludes soft-deleted politicians."""
        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

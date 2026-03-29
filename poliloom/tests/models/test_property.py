"""Tests for the Property model."""

from datetime import datetime, timezone
from poliloom.models import (
    Property,
    PropertyReference,
    PropertyType,
    PropertyComparisonResult,
)


class TestPropertyFindMatching:
    """Test cases for the Property.find_matching() class method.

    Note: Comparison logic is tested in TestPropertyCompareTo.
    These tests focus on the DB integration (no existing property case).
    """

    def test_find_matching_birth_date_no_existing(self, db_session, sample_politician):
        """Test find_matching returns None when no existing date exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert result is None

    def test_find_matching_position_no_existing(
        self, db_session, sample_politician, sample_position
    ):
        """Test find_matching returns None when no existing position exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.POSITION,
            entity_id=sample_position.wikidata_id,
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

        assert result is None

    def test_find_matching_birthplace_no_existing(
        self, db_session, sample_politician, sample_location
    ):
        """Test find_matching returns None when no existing birthplace exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTHPLACE,
            entity_id=sample_location.wikidata_id,
        )

        assert result is None

    def test_find_matching_citizenship_no_existing(
        self, db_session, sample_politician, sample_country
    ):
        """Test find_matching returns None when no existing citizenship exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )

        assert result is None

    def test_find_matching_birth_date_equal(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test find_matching returns existing property when dates are equal."""
        create_birth_date(
            sample_politician, value="+1990-01-01T00:00:00Z", source=sample_source
        )
        db_session.flush()

        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert result is not None
        assert result.value == "+1990-01-01T00:00:00Z"

    def test_find_matching_birth_date_existing_more_precise(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test find_matching returns existing when it's more precise (day vs year)."""
        create_birth_date(
            sample_politician, value="+1990-01-01T00:00:00Z", source=sample_source
        )
        db_session.flush()

        # Search with year-precision date that could match
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,
        )

        assert result is not None
        assert result.value == "+1990-01-01T00:00:00Z"

    def test_find_matching_birth_date_new_more_precise(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test find_matching returns None when new value is more precise."""
        # Existing property has year precision
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,
        )
        db_session.add(prop)
        db_session.flush()

        # Search with day-precision date — new is more precise, so no match
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert result is None

    def test_find_matching_position_equal(
        self,
        db_session,
        sample_politician,
        sample_position,
        sample_source,
        create_position,
    ):
        """Test find_matching returns existing position with matching entity and qualifiers."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-00-00T00:00:00Z", "precision": 9}
                    }
                }
            ]
        }
        create_position(
            sample_politician,
            sample_position,
            source=sample_source,
            qualifiers_json=qualifiers,
        )
        db_session.flush()

        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.POSITION,
            entity_id=sample_position.wikidata_id,
            qualifiers_json=qualifiers,
        )

        assert result is not None
        assert result.entity_id == sample_position.wikidata_id

    def test_find_matching_birthplace_equal(
        self,
        db_session,
        sample_politician,
        sample_location,
        sample_source,
        create_birthplace,
    ):
        """Test find_matching returns existing birthplace with matching entity."""
        create_birthplace(sample_politician, sample_location, source=sample_source)
        db_session.flush()

        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTHPLACE,
            entity_id=sample_location.wikidata_id,
        )

        assert result is not None
        assert result.entity_id == sample_location.wikidata_id

    def test_find_matching_ignores_deleted(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test find_matching ignores soft-deleted properties."""
        prop = create_birth_date(
            sample_politician, value="+1990-01-01T00:00:00Z", source=sample_source
        )
        prop.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert result is None


class TestPropertyAddReference:
    """Tests for Property.add_reference() method."""

    def test_add_reference_creates_new(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test add_reference creates a new PropertyReference."""
        prop = create_birth_date(sample_politician)
        db_session.flush()

        ref = prop.add_reference(db_session, sample_source, ["born in 1980"])
        db_session.flush()

        assert ref is not None
        assert ref.property_id == prop.id
        assert ref.source_id == sample_source.id
        assert ref.supporting_quotes == ["born in 1980"]

    def test_add_reference_idempotent_same_source(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        """Test add_reference updates quotes when same source already linked."""
        prop = create_birth_date(
            sample_politician, source=sample_source, supporting_quotes=["old quote"]
        )
        db_session.flush()

        # Add reference again with same source but different quotes
        prop.add_reference(db_session, sample_source, ["new quote"])
        db_session.flush()

        # Should not create a duplicate
        refs = (
            db_session.query(PropertyReference)
            .filter_by(property_id=prop.id, source_id=sample_source.id)
            .all()
        )
        assert len(refs) == 1
        assert refs[0].supporting_quotes == ["new quote"]

    def test_add_reference_multiple_sources(
        self,
        db_session,
        sample_politician,
        sample_source,
        create_source,
        create_birth_date,
    ):
        """Test add_reference allows multiple different sources."""
        prop = create_birth_date(sample_politician, source=sample_source)
        db_session.flush()

        second_source = create_source(url="https://example.com/other")
        prop.add_reference(db_session, second_source, ["second source quote"])
        db_session.flush()

        refs = db_session.query(PropertyReference).filter_by(property_id=prop.id).all()
        assert len(refs) == 2


class TestPropertyExtractTimeframe:
    """Tests for Property._extract_timeframe_from_qualifiers."""

    def test_extract_both_dates(self):
        """Test extracting both start and end dates."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-15T00:00:00Z", "precision": 11}
                    }
                }
            ],
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-06-30T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is not None
        assert start.precision == 11
        assert end.precision == 11

    def test_extract_start_only(self):
        """Test extracting only start date."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is None

    def test_extract_end_only(self):
        """Test extracting only end date."""
        qualifiers = {
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-12-31T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is None
        assert end is not None

    def test_extract_none_qualifiers(self):
        """Test with None qualifiers."""
        start, end = Property._extract_timeframe_from_qualifiers(None)

        assert start is None
        assert end is None

    def test_extract_empty_qualifiers(self):
        """Test with empty qualifiers dict."""
        start, end = Property._extract_timeframe_from_qualifiers({})

        assert start is None
        assert end is None

    def test_extract_other_qualifiers_only(self):
        """Test with qualifiers that don't include P580/P582."""
        qualifiers = {
            "P585": [  # Point in time
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is None
        assert end is None


class TestPropertyCompareTo:
    """Tests for Property._compare_to method."""

    def test_different_types_no_match(self, sample_politician):
        """Test that different property types don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.DEATH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birth_date_equal_precision(self, sample_politician):
        """Test birth dates with equal precision."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_birth_date_self_more_precise(self, sample_politician):
        """Test birth date where self is more precise."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,  # Day
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-00T00:00:00Z",
            value_precision=10,  # Month
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.SELF_MORE_PRECISE

    def test_birth_date_other_more_precise(self, sample_politician):
        """Test birth date where other is more precise."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-00-00T00:00:00Z",
            value_precision=9,  # Year
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,  # Day
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.OTHER_MORE_PRECISE

    def test_birth_date_different_years_no_match(self, sample_politician):
        """Test birth dates with different years don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1951-05-15T00:00:00Z",
            value_precision=11,
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_position_different_entity_no_match(self, sample_politician):
        """Test positions with different entities don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q456",
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_position_self_has_dates_other_none(self, sample_politician):
        """Test position where self has dates and other doesn't."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
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
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.SELF_MORE_PRECISE

    def test_position_other_has_dates_self_none(self, sample_politician):
        """Test position where other has dates and self doesn't."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
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

        assert prop1._compare_to(prop2) == PropertyComparisonResult.OTHER_MORE_PRECISE

    def test_position_both_no_dates_equal(self, sample_politician):
        """Test positions both without dates are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_position_different_timeframes_no_match(self, sample_politician):
        """Test positions with different timeframes don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
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
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2015-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birthplace_same_entity_equal(self, sample_politician):
        """Test birthplaces with same entity are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_birthplace_different_entity_no_match(self, sample_politician):
        """Test birthplaces with different entities don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q65",
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_citizenship_same_entity_equal(self, sample_politician):
        """Test citizenships with same entity are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

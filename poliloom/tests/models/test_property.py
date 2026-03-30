"""Tests for the Property model."""

from poliloom.enrichment import create_qualifiers_json_for_position
from poliloom.models import (
    Property,
    PropertyType,
    PropertyComparisonResult,
)


class TestPropertyFindMatching:
    """Test cases for the Property.find_matching() class method.

    Note: Comparison logic is tested in TestPropertyCompareTo.
    """

    def test_no_existing(self):
        result = Property.find_matching(
            [],
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        assert result is None

    def test_birth_date_equal(self):
        prop = Property(
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        result = Property.find_matching(
            [prop],
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        assert result is prop

    def test_birth_date_existing_more_precise(self):
        prop = Property(
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        result = Property.find_matching(
            [prop],
            PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,
        )
        assert result is prop

    def test_birth_date_new_more_precise(self):
        prop = Property(
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,
        )
        result = Property.find_matching(
            [prop],
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        assert result is None

    def test_position_equal(self):
        qualifiers = create_qualifiers_json_for_position("2020")
        prop = Property(
            type=PropertyType.POSITION, entity_id="Q123", qualifiers_json=qualifiers
        )
        result = Property.find_matching(
            [prop], PropertyType.POSITION, entity_id="Q123", qualifiers_json=qualifiers
        )
        assert result is prop

    def test_birthplace_equal(self):
        prop = Property(type=PropertyType.BIRTHPLACE, entity_id="Q456")
        result = Property.find_matching(
            [prop], PropertyType.BIRTHPLACE, entity_id="Q456"
        )
        assert result is prop


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


class TestPositionSubsumption:
    """Tests for Property.is_timeframe_subsumed()."""

    def test_two_consecutive_terms_subsume_single_span(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2021-03-31", "2023-10-26"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-10-27"),
            ),
        ]
        assert Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2021-03-31")
        )

    def test_end_date_mismatch_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2021-03-31", "2022-12-31"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2024-01-01", "2024-12-31"
                ),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2021-03-31")
        )

    def test_candidate_start_no_match_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2022-01-01", "2023-06-30"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-07-01"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2020-01-01")
        )

    def test_gap_between_terms_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2015-01-01", "2017-12-31"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2021-01-01"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2015-01-01")
        )

    def test_single_existing_term_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2021-03-31"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2021-03-31")
        )

    def test_candidate_no_start_date_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2021-03-31", "2023-10-26"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-10-27"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position(end_date="2023-10-26")
        )

    def test_candidate_no_dates_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2021-03-31", "2023-10-26"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-10-27"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(existing, None)

    def test_candidate_more_precise_not_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2021"),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2022"),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2021-06-15", "2022-12-01")
        )

    def test_candidate_less_precise_subsumed(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2021-03-31", "2023-10-26"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-10-27"),
            ),
        ]
        assert Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2021")
        )

    def test_three_consecutive_terms_subsume(self):
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2015-01-01", "2018-12-31"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2019-01-01", "2022-12-31"
                ),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2023-01-01"),
            ),
        ]
        assert Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2015-01-01")
        )

    def test_mid_chain_open_end_breaks_chain(self):
        """A term with no end date in the middle of the chain stops the walk."""
        existing = [
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position("2015-01-01"),
            ),
            Property(
                type=PropertyType.POSITION,
                qualifiers_json=create_qualifiers_json_for_position(
                    "2019-01-01", "2022-12-31"
                ),
            ),
        ]
        assert not Property.is_timeframe_subsumed(
            existing, create_qualifiers_json_for_position("2015-01-01", "2022-12-31")
        )

"""Tests for dates module functionality."""

import pytest

from poliloom.dates import (
    validate_date_format,
    normalize_date,
    dates_overlap,
    get_date_range_span,
    is_extension_overlap,
    is_subset_overlap,
)


class TestValidateDateFormat:
    """Test date format validation."""

    def test_valid_year_format(self):
        """Test YYYY format validation."""
        assert validate_date_format("2020") == "2020"

    def test_valid_year_month_format(self):
        """Test YYYY-MM format validation."""
        assert validate_date_format("2020-06") == "2020-06"

    def test_valid_full_date_format(self):
        """Test YYYY-MM-DD format validation."""
        assert validate_date_format("2020-06-15") == "2020-06-15"

    def test_none_input(self):
        """Test None input returns None."""
        assert validate_date_format(None) is None

    def test_invalid_format_raises_error(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_format("06/15/2020")

    def test_empty_string_raises_error(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_format("")


class TestNormalizeDate:
    """Test date normalization."""

    def test_normalize_year_only(self):
        """Test normalizing YYYY to YYYY-MM-DD."""
        assert normalize_date("2020") == "2020-01-01"

    def test_normalize_year_month(self):
        """Test normalizing YYYY-MM to YYYY-MM-DD."""
        assert normalize_date("2020-06") == "2020-06-01"

    def test_normalize_full_date_unchanged(self):
        """Test YYYY-MM-DD remains unchanged."""
        assert normalize_date("2020-06-15") == "2020-06-15"

    def test_normalize_none_input(self):
        """Test None input returns None."""
        assert normalize_date(None) is None


class TestDatesOverlap:
    """Test date range overlap detection."""

    def test_no_overlap_separate_periods(self):
        """Test non-overlapping periods."""
        assert not dates_overlap("2010", "2015", "2020", "2025")

    def test_overlap_partial_end(self):
        """Test partial overlap at end."""
        assert dates_overlap("2010", "2015", "2014", "2018")

    def test_overlap_partial_start(self):
        """Test partial overlap at start."""
        assert dates_overlap("2010", "2015", "2008", "2012")

    def test_overlap_complete_subset(self):
        """Test one period completely within another."""
        assert dates_overlap("2010", "2020", "2012", "2018")

    def test_overlap_complete_extension(self):
        """Test one period completely extends another."""
        assert dates_overlap("2010", "2015", "2008", "2018")

    def test_overlap_same_periods(self):
        """Test identical periods."""
        assert dates_overlap("2010", "2015", "2010", "2015")

    def test_overlap_adjacent_periods_no_overlap(self):
        """Test adjacent periods don't overlap."""
        assert not dates_overlap("2010", "2015", "2016", "2020")

    def test_overlap_touching_periods(self):
        """Test periods that touch at boundary."""
        # 2015-01-01 to 2015-12-31 vs 2016-01-01 to 2020-12-31 should not overlap
        assert not dates_overlap("2015", "2015", "2016", "2020")

    def test_overlap_with_none_end_dates(self):
        """Test overlap with open-ended periods."""
        assert dates_overlap("2010", None, "2015", "2020")

    def test_overlap_with_none_start_dates(self):
        """Test overlap with open-started periods."""
        assert dates_overlap(None, "2015", "2010", "2020")

    def test_overlap_mixed_date_formats(self):
        """Test overlap with different date precisions."""
        assert dates_overlap("2010", "2015-06", "2014-03-15", "2018")


class TestGetDateRangeSpan:
    """Test date range span calculation."""

    def test_span_non_overlapping_periods(self):
        """Test span of non-overlapping periods."""
        start, end = get_date_range_span("2010", "2012", "2015", "2018")
        assert start == "2010"
        assert end == "2018"

    def test_span_overlapping_periods(self):
        """Test span of overlapping periods."""
        start, end = get_date_range_span("2010", "2015", "2012", "2018")
        assert start == "2010"
        assert end == "2018"

    def test_span_with_none_values(self):
        """Test span with None (open-ended) values."""
        start, end = get_date_range_span("2010", None, "2015", "2020")
        assert start == "2010"
        assert end == "2020"  # Should return the latest concrete end date

    def test_span_with_both_none_end_values(self):
        """Test span when both periods have None end dates."""
        start, end = get_date_range_span("2010", None, "2015", None)
        assert start == "2010"
        assert end is None  # No concrete end date available

    def test_span_preserves_original_formats(self):
        """Test that original date formats are preserved."""
        start, end = get_date_range_span("2010", "2015-06", "2012-03-15", "2018")
        assert start == "2010"
        assert end == "2018"

    def test_span_all_none_values(self):
        """Test span with all None values."""
        start, end = get_date_range_span(None, None, None, None)
        assert start is None
        assert end is None


class TestIsExtensionOverlap:
    """Test extension overlap detection."""

    def test_extension_end_only(self):
        """Test extending end date only."""
        assert is_extension_overlap("2010", "2015", "2010", "2018")

    def test_extension_start_only(self):
        """Test extending start date only."""
        assert is_extension_overlap("2010", "2015", "2008", "2015")

    def test_extension_both_directions(self):
        """Test extending both start and end."""
        assert is_extension_overlap("2010", "2015", "2008", "2018")

    def test_not_extension_partial_overlap(self):
        """Test partial overlap is not extension."""
        assert not is_extension_overlap("2010", "2015", "2012", "2018")

    def test_not_extension_shift(self):
        """Test shifting period is not extension."""
        assert not is_extension_overlap("2010", "2015", "2008", "2012")

    def test_not_extension_subset(self):
        """Test subset is not extension."""
        assert not is_extension_overlap("2010", "2015", "2012", "2014")

    def test_extension_with_none_values(self):
        """Test extension with open-ended dates."""
        assert is_extension_overlap("2010", "2015", "2008", None)
        assert is_extension_overlap("2010", "2015", None, "2018")


class TestIsSubsetOverlap:
    """Test subset overlap detection."""

    def test_subset_complete_containment(self):
        """Test period completely within another."""
        assert is_subset_overlap("2010", "2020", "2012", "2018")

    def test_subset_same_start(self):
        """Test subset with same start date."""
        assert is_subset_overlap("2010", "2020", "2010", "2015")

    def test_subset_same_end(self):
        """Test subset with same end date."""
        assert is_subset_overlap("2010", "2020", "2015", "2020")

    def test_subset_identical_periods(self):
        """Test identical periods (subset of itself)."""
        assert is_subset_overlap("2010", "2015", "2010", "2015")

    def test_not_subset_partial_overlap(self):
        """Test partial overlap is not subset."""
        assert not is_subset_overlap("2010", "2015", "2012", "2018")

    def test_not_subset_extension(self):
        """Test extension is not subset."""
        assert not is_subset_overlap("2010", "2015", "2008", "2018")

    def test_not_subset_no_overlap(self):
        """Test non-overlapping periods."""
        assert not is_subset_overlap("2010", "2015", "2020", "2025")

    def test_subset_with_none_values(self):
        """Test subset detection with open-ended dates."""
        assert is_subset_overlap(None, None, "2010", "2015")
        assert not is_subset_overlap("2010", "2015", None, None)


class TestDateComparisonScenarios:
    """Test comprehensive date comparison scenarios."""

    def test_scenario_prime_minister_guatemala_original_issue(self):
        """Test the original issue scenario: Prime Minister of Guatemala overlapping dates."""
        # Existing: 2010-2015, New: 2010-2018 (extends end)
        assert dates_overlap("2010", "2015", "2010", "2018")
        assert is_extension_overlap("2010", "2015", "2010", "2018")
        assert not is_subset_overlap("2010", "2015", "2010", "2018")

    def test_scenario_partial_overlap_end(self):
        """Test partial overlap at end should create separate entities."""
        # Existing: 2010-2015, New: 2014-2018 (partial overlap)
        assert dates_overlap("2010", "2015", "2014", "2018")
        assert not is_extension_overlap("2010", "2015", "2014", "2018")
        assert not is_subset_overlap("2010", "2015", "2014", "2018")

    def test_scenario_gap_bridging(self):
        """Test gap bridging scenario should create separate entities."""
        # Existing: 2010-2012, New: 2011-2015 (partial overlap)
        assert dates_overlap("2010", "2012", "2011", "2015")
        assert not is_extension_overlap("2010", "2012", "2011", "2015")
        assert not is_subset_overlap("2010", "2012", "2011", "2015")

    def test_scenario_subset_within_larger_period(self):
        """Test subset within larger period should be skipped."""
        # Existing: 2010-2018, New: 2012-2015 (subset)
        assert dates_overlap("2010", "2018", "2012", "2015")
        assert not is_extension_overlap("2010", "2018", "2012", "2015")
        assert is_subset_overlap("2010", "2018", "2012", "2015")

    def test_scenario_non_overlapping_separate_terms(self):
        """Test non-overlapping periods should create separate entities."""
        # Existing: 2010-2015, New: 2020-2024 (no overlap)
        assert not dates_overlap("2010", "2015", "2020", "2024")
        assert not is_extension_overlap("2010", "2015", "2020", "2024")
        assert not is_subset_overlap("2010", "2015", "2020", "2024")

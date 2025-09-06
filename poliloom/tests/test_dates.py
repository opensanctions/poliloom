"""Tests for dates module functionality."""

import pytest

from poliloom.dates import (
    validate_date_format,
    get_date_precision,
    get_date_range_precision,
    more_precise_date,
    dates_could_be_same,
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


class TestDatesSameness:
    """Test dates could be same functionality."""

    def test_dates_could_be_same_year_and_specific(self):
        """Test year and specific date within year."""
        assert dates_could_be_same("2025", "2025-03-10")
        assert dates_could_be_same("2025-03-10", "2025")

    def test_dates_could_be_same_different_months(self):
        """Test different months are not same."""
        assert not dates_could_be_same("2024-03", "2024-05-10")

    def test_dates_could_be_same_month_and_specific(self):
        """Test month and specific date within month."""
        assert dates_could_be_same("2025-03", "2025-03-15")
        assert dates_could_be_same("2025-03-15", "2025-03")

    def test_dates_could_be_same_identical(self):
        """Test identical dates."""
        assert dates_could_be_same("2025", "2025")
        assert dates_could_be_same("2025-03-10", "2025-03-10")

    def test_dates_could_be_same_different_years(self):
        """Test different years are not same."""
        assert not dates_could_be_same("2024", "2025-01-01")

    def test_dates_could_be_same_with_none(self):
        """Test None handling."""
        assert not dates_could_be_same(None, "2025")
        assert not dates_could_be_same("2025", None)


class TestDateComparisonScenarios:
    """Test date precision scenarios."""

    def test_scenario_date_precision_preference(self):
        """Test that more precise dates are preferred."""
        # Year vs specific date in same year - could be same
        assert dates_could_be_same("1962", "1962-06-15")

        # Different years - not same
        assert not dates_could_be_same("1961", "1962-06-15")

        # Month vs specific date in same month - could be same
        assert dates_could_be_same("2025-03", "2025-03-15")

        # Different months - not same
        assert not dates_could_be_same("2025-02", "2025-03-15")


class TestDatePrecision:
    """Test date precision functions using Wikidata precision values."""

    def test_get_date_precision_year_only(self):
        """Test precision for year-only dates."""
        assert get_date_precision("1962") == 9

    def test_get_date_precision_year_month(self):
        """Test precision for year-month dates."""
        assert get_date_precision("1962-06") == 10

    def test_get_date_precision_full_date(self):
        """Test precision for full dates."""
        assert get_date_precision("1962-06-15") == 11

    def test_get_date_precision_none(self):
        """Test precision for None dates."""
        assert get_date_precision(None) == 0

    def test_get_date_range_precision(self):
        """Test precision calculation for date ranges."""
        start_prec, end_prec = get_date_range_precision("1962", "1965-12-31")
        assert start_prec == 9  # Year precision
        assert end_prec == 11  # Day precision

    def test_more_precise_date_higher_precision(self):
        """Test selecting more precise date."""
        assert more_precise_date("1962", "1962-06-15") == "1962-06-15"
        assert more_precise_date("1962-06-15", "1962") == "1962-06-15"

    def test_more_precise_date_equal_precision(self):
        """Test equal precision returns None."""
        assert more_precise_date("1962", "1965") is None
        assert more_precise_date("1962-06-15", "1965-12-31") is None

    def test_more_precise_date_with_none(self):
        """Test handling None values."""
        assert more_precise_date(None, "1962") == "1962"
        assert more_precise_date("1962", None) == "1962"
        assert more_precise_date(None, None) is None

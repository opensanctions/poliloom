"""Tests for dates module functionality."""

import pytest

from poliloom.wikidata_date import WikidataDate


class TestValidateDateFormat:
    """Test date format validation."""

    def test_valid_year_format(self):
        """Test YYYY format validation."""
        assert WikidataDate.validate_date_format("2020") == "2020"

    def test_valid_year_month_format(self):
        """Test YYYY-MM format validation."""
        assert WikidataDate.validate_date_format("2020-06") == "2020-06"

    def test_valid_full_date_format(self):
        """Test YYYY-MM-DD format validation."""
        assert WikidataDate.validate_date_format("2020-06-15") == "2020-06-15"

    def test_invalid_format_raises_error(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            WikidataDate.validate_date_format("06/15/2020")

    def test_empty_string_raises_error(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            WikidataDate.validate_date_format("")


class TestDatesSameness:
    """Test dates could be same functionality."""

    def test_dates_could_be_same_year_and_specific(self):
        """Test year and specific date within year."""
        year_date = WikidataDate.from_date_string("2025")
        specific_date = WikidataDate.from_date_string("2025-03-10")
        assert WikidataDate.dates_could_be_same(year_date, specific_date)
        assert WikidataDate.dates_could_be_same(specific_date, year_date)

    def test_dates_could_be_same_different_months(self):
        """Test different months are not same."""
        march_date = WikidataDate.from_date_string("2024-03")
        may_date = WikidataDate.from_date_string("2024-05-10")
        assert not WikidataDate.dates_could_be_same(march_date, may_date)

    def test_dates_could_be_same_month_and_specific(self):
        """Test month and specific date within month."""
        month_date = WikidataDate.from_date_string("2025-03")
        specific_date = WikidataDate.from_date_string("2025-03-15")
        assert WikidataDate.dates_could_be_same(month_date, specific_date)
        assert WikidataDate.dates_could_be_same(specific_date, month_date)

    def test_dates_could_be_same_identical(self):
        """Test identical dates."""
        year1 = WikidataDate.from_date_string("2025")
        year2 = WikidataDate.from_date_string("2025")
        date1 = WikidataDate.from_date_string("2025-03-10")
        date2 = WikidataDate.from_date_string("2025-03-10")
        assert WikidataDate.dates_could_be_same(year1, year2)
        assert WikidataDate.dates_could_be_same(date1, date2)

    def test_dates_could_be_same_different_years(self):
        """Test different years are not same."""
        date1 = WikidataDate.from_date_string("2024")
        date2 = WikidataDate.from_date_string("2025-01-01")
        assert not WikidataDate.dates_could_be_same(date1, date2)

    def test_dates_could_be_same_with_none(self):
        """Test None handling."""
        date = WikidataDate.from_date_string("2025")
        assert not WikidataDate.dates_could_be_same(None, date)
        assert not WikidataDate.dates_could_be_same(date, None)
        assert not WikidataDate.dates_could_be_same(None, None)


class TestDateComparisonScenarios:
    """Test date precision scenarios."""

    def test_scenario_date_precision_preference(self):
        """Test that more precise dates are preferred."""
        # Year vs specific date in same year - could be same
        year1962 = WikidataDate.from_date_string("1962")
        date1962 = WikidataDate.from_date_string("1962-06-15")
        assert WikidataDate.dates_could_be_same(year1962, date1962)

        # Different years - not same
        year1961 = WikidataDate.from_date_string("1961")
        assert not WikidataDate.dates_could_be_same(year1961, date1962)

        # Month vs specific date in same month - could be same
        month_march = WikidataDate.from_date_string("2025-03")
        date_march = WikidataDate.from_date_string("2025-03-15")
        assert WikidataDate.dates_could_be_same(month_march, date_march)

        # Different months - not same
        month_feb = WikidataDate.from_date_string("2025-02")
        assert not WikidataDate.dates_could_be_same(month_feb, date_march)


class TestDatePrecision:
    """Test date precision functions using Wikidata precision values."""

    def test_get_date_precision_year_only(self):
        """Test precision for year-only dates."""
        assert WikidataDate.get_date_precision("1962") == 9

    def test_get_date_precision_year_month(self):
        """Test precision for year-month dates."""
        assert WikidataDate.get_date_precision("1962-06") == 10

    def test_get_date_precision_full_date(self):
        """Test precision for full dates."""
        assert WikidataDate.get_date_precision("1962-06-15") == 11

    def test_get_date_precision_none(self):
        """Test precision for None dates."""
        assert WikidataDate.get_date_precision(None) == 0

    def test_get_date_range_precision(self):
        """Test precision calculation for date ranges."""
        start_prec = WikidataDate.get_date_precision("1962")
        end_prec = WikidataDate.get_date_precision("1965-12-31")
        assert start_prec == 9  # Year precision
        assert end_prec == 11  # Day precision

    def test_more_precise_date_higher_precision(self):
        """Test selecting more precise date."""
        year_date = WikidataDate.from_date_string("1962")
        specific_date = WikidataDate.from_date_string("1962-06-15")
        assert WikidataDate.more_precise_date(year_date, specific_date) == specific_date
        assert WikidataDate.more_precise_date(specific_date, year_date) == specific_date

    def test_more_precise_date_equal_precision(self):
        """Test equal precision returns None."""
        year1 = WikidataDate.from_date_string("1962")
        year2 = WikidataDate.from_date_string("1965")
        date1 = WikidataDate.from_date_string("1962-06-15")
        date2 = WikidataDate.from_date_string("1965-12-31")
        assert WikidataDate.more_precise_date(year1, year2) is None
        assert WikidataDate.more_precise_date(date1, date2) is None

    def test_more_precise_date_with_none(self):
        """Test handling None values."""
        date = WikidataDate.from_date_string("1962")
        assert WikidataDate.more_precise_date(None, date) == date
        assert WikidataDate.more_precise_date(date, None) == date
        assert WikidataDate.more_precise_date(None, None) is None

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
        # Two None dates should be considered the same (both unspecified)
        assert WikidataDate.dates_could_be_same(None, None)

    def test_dates_could_be_same_year_different_timestamp_formats(self):
        """Test same year with different Wikidata timestamp formats."""
        # From production: existing Wikidata date (Jan 1st format)
        existing_date = WikidataDate.from_wikidata_time("+1962-01-01T00:00:00Z", 9)

        # From production: new Wikipedia extracted date (00-00 format)
        new_date = WikidataDate.from_wikidata_time("+1962-00-00T00:00:00Z", 9)

        # Both have year precision (9) and same year - should be considered same
        assert WikidataDate.dates_could_be_same(existing_date, new_date)

    def test_dates_could_be_same_decade_precision(self):
        """Test decade precision (8) dates."""
        # 2010s decade
        decade1 = WikidataDate.from_wikidata_time("+2010-00-00T00:00:00Z", 8)
        decade2 = WikidataDate.from_wikidata_time("+2010-00-00T00:00:00Z", 8)

        # Same decade should be considered same
        assert WikidataDate.dates_could_be_same(decade1, decade2)

    def test_dates_could_be_same_century_precision(self):
        """Test century precision (7) dates."""
        # 19th century
        century1 = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)
        century2 = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)

        # Same century should be considered same
        assert WikidataDate.dates_could_be_same(century1, century2)

    def test_dates_could_be_same_millennium_precision(self):
        """Test millennium precision (6) dates."""
        # Second millennium
        millennium1 = WikidataDate.from_wikidata_time("+1500-00-00T00:00:00Z", 6)
        millennium2 = WikidataDate.from_wikidata_time("+1500-00-00T00:00:00Z", 6)

        # Same millennium should be considered same
        assert WikidataDate.dates_could_be_same(millennium1, millennium2)

    def test_dates_could_be_same_cross_precision_year_vs_decade(self):
        """Test year precision (enrichment) vs decade precision (Wikidata)."""
        # Year 2015 from enrichment
        year_date = WikidataDate.from_wikidata_time("+2015-00-00T00:00:00Z", 9)

        # 2010s decade from Wikidata
        decade_date = WikidataDate.from_wikidata_time("+2010-00-00T00:00:00Z", 8)

        # 2015 is within the 2010s decade - should be considered same
        assert WikidataDate.dates_could_be_same(year_date, decade_date)
        assert WikidataDate.dates_could_be_same(decade_date, year_date)

    def test_dates_could_be_same_cross_precision_year_vs_century(self):
        """Test year precision (enrichment) vs century precision (Wikidata)."""
        # Year 1850 from enrichment
        year_date = WikidataDate.from_wikidata_time("+1850-00-00T00:00:00Z", 9)

        # 19th century from Wikidata (represented as 1801)
        century_date = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)

        # 1850 is within the 19th century - should be considered same
        assert WikidataDate.dates_could_be_same(year_date, century_date)
        assert WikidataDate.dates_could_be_same(century_date, year_date)

    def test_dates_could_be_same_cross_precision_month_vs_decade(self):
        """Test month precision (enrichment) vs decade precision (Wikidata)."""
        # June 2018 from enrichment
        month_date = WikidataDate.from_wikidata_time("+2018-06-00T00:00:00Z", 10)

        # 2010s decade from Wikidata
        decade_date = WikidataDate.from_wikidata_time("+2010-00-00T00:00:00Z", 8)

        # June 2018 is within the 2010s decade - should be considered same
        assert WikidataDate.dates_could_be_same(month_date, decade_date)
        assert WikidataDate.dates_could_be_same(decade_date, month_date)

    def test_dates_could_be_same_cross_precision_day_vs_century(self):
        """Test day precision (enrichment) vs century precision (Wikidata)."""
        # Specific date in 19th century from enrichment
        day_date = WikidataDate.from_wikidata_time("+1875-03-15T00:00:00Z", 11)

        # 19th century from Wikidata
        century_date = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)

        # March 15, 1875 is within the 19th century - should be considered same
        assert WikidataDate.dates_could_be_same(day_date, century_date)
        assert WikidataDate.dates_could_be_same(century_date, day_date)

    def test_dates_could_be_same_cross_precision_different_periods(self):
        """Test cross-precision dates that are NOT in the same period."""
        # Year 2005 from enrichment
        year_2005 = WikidataDate.from_wikidata_time("+2005-00-00T00:00:00Z", 9)

        # 2010s decade from Wikidata
        decade_2010s = WikidataDate.from_wikidata_time("+2010-00-00T00:00:00Z", 8)

        # 2005 is NOT in the 2010s decade - should be different
        assert not WikidataDate.dates_could_be_same(year_2005, decade_2010s)

        # Year 1750 from enrichment
        year_1750 = WikidataDate.from_wikidata_time("+1750-00-00T00:00:00Z", 9)

        # 19th century from Wikidata
        century_19th = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)

        # 1750 is NOT in the 19th century (it's 18th century) - should be different
        assert not WikidataDate.dates_could_be_same(year_1750, century_19th)

    def test_dates_could_be_same_cross_precision_day_vs_month(self):
        """Test day precision vs month precision (both from enrichment)."""
        # Specific day in March 2020
        day_date = WikidataDate.from_wikidata_time("+2020-03-15T00:00:00Z", 11)

        # March 2020 (month precision)
        month_date = WikidataDate.from_wikidata_time("+2020-03-00T00:00:00Z", 10)

        # March 15, 2020 is within March 2020 - should be considered same
        assert WikidataDate.dates_could_be_same(day_date, month_date)
        assert WikidataDate.dates_could_be_same(month_date, day_date)

    def test_dates_could_be_same_cross_precision_day_vs_year(self):
        """Test day precision vs year precision (both from enrichment)."""
        # Specific day in 2019
        day_date = WikidataDate.from_wikidata_time("+2019-07-20T00:00:00Z", 11)

        # Year 2019
        year_date = WikidataDate.from_wikidata_time("+2019-00-00T00:00:00Z", 9)

        # July 20, 2019 is within 2019 - should be considered same
        assert WikidataDate.dates_could_be_same(day_date, year_date)
        assert WikidataDate.dates_could_be_same(year_date, day_date)

    def test_dates_could_be_same_cross_precision_month_vs_year(self):
        """Test month precision vs year precision (both from enrichment)."""
        # September 2021
        month_date = WikidataDate.from_wikidata_time("+2021-09-00T00:00:00Z", 10)

        # Year 2021
        year_date = WikidataDate.from_wikidata_time("+2021-00-00T00:00:00Z", 9)

        # September 2021 is within 2021 - should be considered same
        assert WikidataDate.dates_could_be_same(month_date, year_date)
        assert WikidataDate.dates_could_be_same(year_date, month_date)

    def test_dates_could_be_same_cross_precision_enrichment_different_periods(self):
        """Test cross-precision enrichment dates that are NOT in the same period."""
        # Day in March vs month of April (different months)
        day_march = WikidataDate.from_wikidata_time("+2020-03-15T00:00:00Z", 11)
        month_april = WikidataDate.from_wikidata_time("+2020-04-00T00:00:00Z", 10)

        assert not WikidataDate.dates_could_be_same(day_march, month_april)

        # Day in 2019 vs year 2020 (different years)
        day_2019 = WikidataDate.from_wikidata_time("+2019-12-31T00:00:00Z", 11)
        year_2020 = WikidataDate.from_wikidata_time("+2020-00-00T00:00:00Z", 9)

        assert not WikidataDate.dates_could_be_same(day_2019, year_2020)

        # Month in 2018 vs year 2019 (different years)
        month_2018 = WikidataDate.from_wikidata_time("+2018-11-00T00:00:00Z", 10)
        year_2019 = WikidataDate.from_wikidata_time("+2019-00-00T00:00:00Z", 9)

        assert not WikidataDate.dates_could_be_same(month_2018, year_2019)

    def test_dates_could_be_same_unsupported_precision_levels(self):
        """Test that unsupported precision levels always return False."""
        # Test precision 4 (hundred thousand years) vs precision 7 (century)
        hundred_thousand_years = WikidataDate.from_wikidata_time(
            "+2500000-01-01T00:00:00Z", 4
        )
        century_19th = WikidataDate.from_wikidata_time("+1801-00-00T00:00:00Z", 7)

        assert not WikidataDate.dates_could_be_same(
            hundred_thousand_years, century_19th
        )
        assert not WikidataDate.dates_could_be_same(
            century_19th, hundred_thousand_years
        )

        # Test precision 0 (billion years) vs precision 9 (year)
        billion_years = WikidataDate.from_wikidata_time(
            "+5000000000-00-00T00:00:00Z", 0
        )
        year_2020 = WikidataDate.from_wikidata_time("+2020-00-00T00:00:00Z", 9)

        assert not WikidataDate.dates_could_be_same(billion_years, year_2020)
        assert not WikidataDate.dates_could_be_same(year_2020, billion_years)

        # Test precision 5 (ten thousand years) vs precision 10 (month)
        ten_thousand_years = WikidataDate.from_wikidata_time(
            "+10000-01-01T00:00:00Z", 5
        )
        month_precision = WikidataDate.from_wikidata_time("+2020-03-00T00:00:00Z", 10)

        assert not WikidataDate.dates_could_be_same(ten_thousand_years, month_precision)
        assert not WikidataDate.dates_could_be_same(month_precision, ten_thousand_years)

        # Test two unsupported precisions (both should return False)
        precision_3 = WikidataDate.from_wikidata_time("+13798000000-01-01T00:00:00Z", 3)
        precision_1 = WikidataDate.from_wikidata_time("+100000000-01-01T00:00:00Z", 1)

        assert not WikidataDate.dates_could_be_same(precision_3, precision_1)


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

"""Date utility functions for handling politician position timeframes."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, Any


@dataclass
class WikidataDate:
    """Represents a Wikidata date with precision and BCE handling."""

    time_string: str  # Raw Wikidata time string (e.g., "+1970-06-15T00:00:00Z", "-0347-10-15T00:00:00Z")
    precision: int  # Wikidata precision level (9=year, 10=month, 11=day)

    @property
    def is_bce(self) -> bool:
        """True if this is a BCE (Before Common Era) date."""
        return self.time_string.startswith("-")

    def to_python_date(self) -> Optional[date]:
        """Convert to Python date object.

        Returns None for BCE dates or if parsing fails.
        For year/month precision, uses first day of year/month.
        """
        if self.is_bce:
            return None

        try:
            from datetime import datetime

            # Remove the + sign: "+2011-00-00T00:05:23Z" -> "2011-00-00T00:05:23Z"
            iso_string = self.time_string[1:]

            # Replace -00- with valid values for parsing
            iso_string = iso_string.replace("-00-", "-01-").replace("-00T", "-01T")

            # Parse and return date part
            dt = datetime.fromisoformat(iso_string)
            return dt.date()
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_wikidata_time(
        cls, time_value: str, precision: int
    ) -> Optional["WikidataDate"]:
        """Create WikidataDate from Wikidata time format.

        Args:
            time_value: Wikidata time string like "+1970-06-15T00:00:00Z" or "-0347-00-00T00:00:00Z"
            precision: Wikidata precision value (9=year, 10=month, 11=day)

        Returns:
            WikidataDate object or None if invalid format
        """
        if not time_value or not time_value.startswith(("+", "-")):
            return None

        return cls(time_string=time_value, precision=precision)

    @classmethod
    def from_date_string(cls, date_value: str) -> Optional["WikidataDate"]:
        """Create WikidataDate from a date string in YYYY, YYYY-MM, or YYYY-MM-DD format.

        Args:
            date_value: Date string in YYYY, YYYY-MM, or YYYY-MM-DD format

        Returns:
            WikidataDate object or None if parsing fails
        """
        try:
            validated_date = WikidataDate.validate_date_format(date_value)
            precision = WikidataDate.get_date_precision(validated_date)

            # Convert to Wikidata time string format
            parts = validated_date.split("-")
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 0
            day = int(parts[2]) if len(parts) > 2 else 0

            # Format as Wikidata time string
            if precision == 11:  # Day precision (YYYY-MM-DD)
                time_str = f"+{year:04d}-{month:02d}-{day:02d}T00:00:00Z"
            elif precision == 10:  # Month precision (YYYY-MM)
                time_str = f"+{year:04d}-{month:02d}-00T00:00:00Z"
            elif precision == 9:  # Year precision (YYYY)
                time_str = f"+{year:04d}-00-00T00:00:00Z"
            else:
                raise ValueError(f"Unsupported date precision {precision}")

            return cls(time_string=time_str, precision=precision)
        except ValueError:
            return None

    def to_wikidata_value(self) -> Dict[str, Any]:
        """Convert this WikidataDate to core Wikidata time values.

        Returns:
            Dict with time, precision, timezone, before, after, and calendarmodel
        """
        return {
            "time": self.time_string,
            "timezone": 0,
            "before": 0,
            "after": 0,
            "precision": self.precision,
            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
        }

    def to_wikidata_qualifier(self) -> Dict[str, Any]:
        """Convert this WikidataDate to Wikidata qualifier/reference format.

        Returns:
            Full Wikidata time structure with datatype, snaktype, and datavalue
        """
        return {
            "datatype": "time",
            "snaktype": "value",
            "datavalue": {
                "type": "time",
                "value": self.to_wikidata_value(),
            },
        }

    def extract_date_parts(self) -> tuple[int, Optional[int], Optional[int]]:
        """Extract year, month, day from the date string.

        Returns:
            Tuple of (year, month, day) where month and day can be None if not specified
        """
        # Remove sign and time portion: "+2020-03-15T00:00:00Z" -> "2020-03-15"
        date_part = self.time_string.split("T")[0][1:]
        parts = date_part.split("-")
        year = int(parts[0])
        month = int(parts[1]) if parts[1] != "00" else None
        day = int(parts[2]) if len(parts) > 2 and parts[2] != "00" else None
        return year, month, day

    @staticmethod
    def dates_could_be_same(
        date1: Optional["WikidataDate"], date2: Optional["WikidataDate"]
    ) -> bool:
        """
        Check if two WikidataDate objects could refer to the same time period.

        Args:
            date1: First WikidataDate object
            date2: Second WikidataDate object

        Examples:
        - Year precision and day precision in same year could be the same
        - Month precision and day precision in same month could be the same
        - Different months/years are not the same
        """
        if date1 is None and date2 is None:
            return True  # Both None means same (no date specified)
        if date1 is None or date2 is None:
            return False  # One None, one specified means different

        # Extract year, month, day from both dates
        year1, month1, day1 = date1.extract_date_parts()
        year2, month2, day2 = date2.extract_date_parts()

        # Determine which date is more precise
        if date1.precision == date2.precision:
            # Same precision - direct comparison based on precision level
            if date1.precision <= 8:  # Decade, century, millennium
                return year1 == year2
            elif date1.precision == 9:  # Year precision
                return year1 == year2
            elif date1.precision == 10:  # Month precision
                return year1 == year2 and month1 == month2
            else:  # Day precision (11) or higher
                return year1 == year2 and month1 == month2 and day1 == day2

        # Different precisions - check if more precise date falls within less precise period
        more_precise_date = date1 if date1.precision > date2.precision else date2
        less_precise_date = date2 if date1.precision > date2.precision else date1

        more_year, more_month, more_day = more_precise_date.extract_date_parts()
        less_year, less_month, less_day = less_precise_date.extract_date_parts()

        if less_precise_date.precision == 6:  # Millennium precision
            millennium_start = ((less_year - 1) // 1000) * 1000 + 1
            millennium_end = millennium_start + 999
            return millennium_start <= more_year <= millennium_end
        elif less_precise_date.precision == 7:  # Century precision
            century_start = less_year
            century_end = century_start + 99
            return century_start <= more_year <= century_end
        elif less_precise_date.precision == 8:  # Decade precision
            decade_start = (less_year // 10) * 10
            return decade_start <= more_year < decade_start + 10
        elif less_precise_date.precision == 9:  # Year precision
            return more_year == less_year
        elif less_precise_date.precision == 10:  # Month precision
            return more_year == less_year and more_month == less_month
        elif less_precise_date.precision == 11:  # Day precision
            return (
                more_year == less_year
                and more_month == less_month
                and more_day == less_day
            )
        else:
            # Unsupported precision levels (0-5, 12+) - assume dates are not the same
            return False

    @staticmethod
    def more_precise_date(
        date1: Optional["WikidataDate"], date2: Optional["WikidataDate"]
    ) -> Optional["WikidataDate"]:
        """Return the WikidataDate with higher precision, or None if equal precision."""
        if date1 is None and date2 is None:
            return None
        if date1 is None:
            return date2
        if date2 is None:
            return date1

        if date1.precision > date2.precision:
            return date1
        elif date2.precision > date1.precision:
            return date2
        else:
            return None

    @staticmethod
    def validate_date_format(date_str: str) -> str:
        """Validate date format: YYYY, YYYY-MM, or YYYY-MM-DD."""
        # Allow the three valid formats
        patterns = [
            r"^\d{4}$",  # YYYY
            r"^\d{4}-\d{2}$",  # YYYY-MM
            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
        ]

        for pattern in patterns:
            if re.match(pattern, date_str):
                return date_str

        raise ValueError(
            f"Invalid date format: '{date_str}'. Must be YYYY, YYYY-MM, or YYYY-MM-DD"
        )

    @staticmethod
    def get_date_precision(date_str: Optional[str]) -> int:
        """
        Get the Wikidata precision value for a date string.

        Args:
            date_str: Date in YYYY, YYYY-MM, or YYYY-MM-DD format

        Returns:
            Wikidata precision value: 9 (year), 10 (month), 11 (day), 0 (None/unknown)
        """
        if date_str is None:
            return 0
        if len(date_str) == 4:  # YYYY
            return 9  # Year precision in Wikidata
        elif len(date_str) == 7:  # YYYY-MM
            return 10  # Month precision in Wikidata
        elif len(date_str) == 10:  # YYYY-MM-DD
            return 11  # Day precision in Wikidata
        return 0

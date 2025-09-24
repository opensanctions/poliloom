"""Date utility functions for handling politician position timeframes."""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class WikidataDate:
    """Represents a Wikidata date with precision and BCE handling."""

    date: str  # The date part without sign (e.g., "0347-10-15", "1970", "1970-06")
    precision: int  # Wikidata precision level (9=year, 10=month, 11=day)
    is_bce: bool  # True if this is a BCE (Before Common Era) date

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

        is_bce = time_value.startswith("-")
        # Split on T to remove time portion, then remove the +/- sign
        date_part = time_value.split("T")[0][1:]

        # Truncate based on precision
        if precision >= 11:  # day precision
            pass  # Full YYYY-MM-DD
        elif precision == 10:  # month precision
            date_part = date_part[:7]  # YYYY-MM
        elif precision == 9:  # year precision
            date_part = date_part[:4]  # YYYY
        elif precision == 8:  # decade precision
            date_part = date_part[:4]  # YYYY (treat decade as year)
        elif precision == 7:  # century precision
            date_part = date_part[:4]  # YYYY (treat century as year)
        elif precision == 6:  # millennium precision
            date_part = date_part[:4]  # YYYY (treat millennium as year)
        else:
            # Lower precision not commonly used for dates
            return None

        return cls(date=date_part, precision=precision, is_bce=is_bce)

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
            return cls(date=validated_date, precision=precision, is_bce=False)
        except ValueError:
            return None

    def to_wikidata_value(self) -> Dict[str, Any]:
        """Convert this WikidataDate to core Wikidata time values.

        Returns:
            Dict with time, precision, timezone, before, after, and calendarmodel
        """
        # Parse the components
        parts = self.date.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 0
        day = int(parts[2]) if len(parts) > 2 else 0

        # Handle BCE dates
        sign = "-" if self.is_bce else "+"

        # Format time string based on precision
        if self.precision == 11:  # Day precision (YYYY-MM-DD)
            time_str = f"{sign}{year:04d}-{month:02d}-{day:02d}T00:00:00Z"
        elif self.precision == 10:  # Month precision (YYYY-MM)
            time_str = f"{sign}{year:04d}-{month:02d}-00T00:00:00Z"
        elif self.precision == 9:  # Year precision (YYYY)
            time_str = f"{sign}{year:04d}-00-00T00:00:00Z"
        else:
            raise ValueError(f"Unsupported date precision {self.precision}")

        return {
            "time": time_str,
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

    def is_more_precise_than(self, other: "WikidataDate") -> bool:
        """Check if this date has higher precision than another date."""
        return self.precision > other.precision

    def get_more_precise(self, other: "WikidataDate") -> Optional["WikidataDate"]:
        """Return the date with higher precision, or None if equal precision."""
        if self.precision > other.precision:
            return self
        elif other.precision > self.precision:
            return other
        else:
            return None

    def could_be_same_as(self, other: "WikidataDate") -> bool:
        """
        Check if this date could refer to the same time period as another date.

        Examples:
        - "2025" and "2025-03-10" could be the same (specific date within year)
        - "2024-03" and "2024-05-10" are not the same (different months)
        - "2025-03" and "2025-03-15" could be the same (specific date within month)
        """
        # Get the longer (more specific) and shorter (less specific) dates
        if len(self.date) > len(other.date):
            specific, general = self.date, other.date
        elif len(other.date) > len(self.date):
            specific, general = other.date, self.date
        else:
            # Same length - must be exact match
            return self.date == other.date

        # Check if the specific date starts with the general date
        return specific.startswith(general)

    @staticmethod
    def dates_could_be_same(date1: Optional[str], date2: Optional[str]) -> bool:
        """
        Check if two date strings could refer to the same time period.

        Examples:
        - "2025" and "2025-03-10" could be the same (specific date within year)
        - "2024-03" and "2024-05-10" are not the same (different months)
        - "2025-03" and "2025-03-15" could be the same (specific date within month)
        """
        if date1 is None or date2 is None:
            return False

        # Get the longer (more specific) and shorter (less specific) dates
        if len(date1) > len(date2):
            specific, general = date1, date2
        elif len(date2) > len(date1):
            specific, general = date2, date1
        else:
            # Same length - must be exact match
            return date1 == date2

        # Check if the specific date starts with the general date
        return specific.startswith(general)

    @staticmethod
    def more_precise_date(date1: Optional[str], date2: Optional[str]) -> Optional[str]:
        """Return the date with higher precision, or None if equal precision."""
        if date1 is None and date2 is None:
            return None
        if date1 is None:
            return date2
        if date2 is None:
            return date1

        prec1 = WikidataDate.get_date_precision(date1)
        prec2 = WikidataDate.get_date_precision(date2)

        if prec1 > prec2:
            return date1
        elif prec2 > prec1:
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

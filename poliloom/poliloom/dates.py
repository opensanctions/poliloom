"""Date utility functions for handling politician position timeframes."""

import re
from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class WikidataDate:
    """Represents a Wikidata date with precision and BCE handling."""

    date: str  # The date part without sign (e.g., "0347-10-15", "1970", "1970-06")
    raw_date: str  # Original date string with sign (e.g., "-0347-10-15", "+1970-06-15")
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
        # Split on T to remove time portion
        date_with_sign = time_value.split("T")[0]
        date_without_sign = date_with_sign[1:]  # Remove the + or - sign

        # Truncate based on precision
        if precision >= 11:  # day precision
            date_part = date_without_sign  # Full YYYY-MM-DD
            raw_part = date_with_sign
        elif precision == 10:  # month precision
            date_part = date_without_sign[:7]  # YYYY-MM
            raw_part = date_with_sign[:8] if is_bce else date_with_sign[:7]
        elif precision == 9:  # year precision
            date_part = date_without_sign[:4]  # YYYY
            raw_part = date_with_sign[:5] if is_bce else date_with_sign[:4]
        else:
            # Lower precision not commonly used for dates
            return None

        return cls(
            date=date_part, raw_date=raw_part, precision=precision, is_bce=is_bce
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "date": self.date,
            "raw_date": self.raw_date,
            "precision": self.precision,
            "is_bce": self.is_bce,
        }


def validate_date_format(date_str: Optional[str]) -> Optional[str]:
    """Validate date format: YYYY, YYYY-MM, or YYYY-MM-DD."""
    if date_str is None:
        return None

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


def get_date_range_precision(
    start: Optional[str], end: Optional[str]
) -> tuple[int, int]:
    """
    Get the Wikidata precision values for a date range.

    Args:
        start: Start date
        end: End date

    Returns:
        Tuple of (start_precision, end_precision)
    """
    return get_date_precision(start), get_date_precision(end)


def more_precise_date(date1: Optional[str], date2: Optional[str]) -> Optional[str]:
    """Return the date with higher precision, or None if equal precision."""
    if date1 is None and date2 is None:
        return None
    if date1 is None:
        return date2
    if date2 is None:
        return date1

    prec1 = get_date_precision(date1)
    prec2 = get_date_precision(date2)

    if prec1 > prec2:
        return date1
    elif prec2 > prec1:
        return date2
    else:
        return None


def dates_could_be_same(date1: Optional[str], date2: Optional[str]) -> bool:
    """
    Check if two dates could refer to the same time period.

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
    # "2025-03-10" starts with "2025" -> could be same
    # "2025-03-10" starts with "2025-03" -> could be same
    # "2025-05-10" does not start with "2025-03" -> not same
    return specific.startswith(general)

"""Date utility functions for handling politician position timeframes."""

import re
from typing import Optional


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


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalize date string to YYYY-MM-DD format for comparison.

    Args:
        date_str: Date in YYYY, YYYY-MM, or YYYY-MM-DD format

    Returns:
        Date in YYYY-MM-DD format, or None if input is None
    """
    if date_str is None:
        return None
    if len(date_str) == 4:  # YYYY
        return f"{date_str}-01-01"
    elif len(date_str) == 7:  # YYYY-MM
        return f"{date_str}-01"
    return date_str  # YYYY-MM-DD already normalized


def dates_overlap(
    start1: Optional[str],
    end1: Optional[str],
    start2: Optional[str],
    end2: Optional[str],
) -> bool:
    """
    Check if two date ranges overlap.

    Args:
        start1, end1: First date range (None means open-ended)
        start2, end2: Second date range (None means open-ended)

    Returns:
        True if the date ranges overlap, False otherwise
    """
    # Normalize dates to YYYY-MM-DD format for comparison
    norm_start1 = normalize_date(start1)
    norm_end1 = normalize_date(end1)
    norm_start2 = normalize_date(start2)
    norm_end2 = normalize_date(end2)

    # Handle open-ended ranges (None means ongoing/infinite)
    # If no end date, treat as ongoing (far future date)
    far_future = "9999-12-31"
    norm_end1 = norm_end1 or far_future
    norm_end2 = norm_end2 or far_future

    # If no start date, treat as beginning of time
    far_past = "0001-01-01"
    norm_start1 = norm_start1 or far_past
    norm_start2 = norm_start2 or far_past

    # Check for overlap: ranges overlap if start of one is before end of other, and vice versa
    return norm_start1 <= norm_end2 and norm_start2 <= norm_end1


def get_date_range_span(
    start1: Optional[str],
    end1: Optional[str],
    start2: Optional[str],
    end2: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Get the union (total span) of two date ranges.

    Args:
        start1, end1: First date range
        start2, end2: Second date range

    Returns:
        Tuple of (earliest_start, latest_end) that spans both ranges
    """
    # Collect all non-None dates with their normalized versions for comparison
    start_dates = []
    end_dates = []

    if start1:
        start_dates.append((start1, normalize_date(start1)))
    if start2:
        start_dates.append((start2, normalize_date(start2)))
    if end1:
        end_dates.append((end1, normalize_date(end1)))
    if end2:
        end_dates.append((end2, normalize_date(end2)))

    # Find earliest start (minimum normalized date)
    earliest_start = None
    if start_dates:
        earliest_start = min(start_dates, key=lambda x: x[1])[
            0
        ]  # Return original format

    # Find latest end (maximum normalized date)
    latest_end = None
    if end_dates:
        latest_end = max(end_dates, key=lambda x: x[1])[0]  # Return original format

    return earliest_start, latest_end


def is_extension_overlap(
    existing_start: Optional[str],
    existing_end: Optional[str],
    new_start: Optional[str],
    new_end: Optional[str],
) -> bool:
    """
    Check if the new period extends the existing period (same start OR same end, but longer).

    Extension cases:
    - Existing: 2010-2015, New: 2010-2018 (extends end)
    - Existing: 2010-2015, New: 2008-2015 (extends start)
    - Existing: 2010-2015, New: 2008-2018 (extends both)
    """
    norm_existing_start = normalize_date(existing_start)
    norm_existing_end = normalize_date(existing_end)
    norm_new_start = normalize_date(new_start)
    norm_new_end = normalize_date(new_end)

    # Handle None values
    far_future = "9999-12-31"
    far_past = "0001-01-01"

    norm_existing_start = norm_existing_start or far_past
    norm_existing_end = norm_existing_end or far_future
    norm_new_start = norm_new_start or far_past
    norm_new_end = norm_new_end or far_future

    # Extension: starts at same time or earlier AND ends at same time or later
    starts_same_or_earlier = norm_new_start <= norm_existing_start
    ends_same_or_later = norm_new_end >= norm_existing_end

    # Must extend in at least one direction
    extends_start = norm_new_start < norm_existing_start
    extends_end = norm_new_end > norm_existing_end

    return (
        starts_same_or_earlier and ends_same_or_later and (extends_start or extends_end)
    )


def is_subset_overlap(
    existing_start: Optional[str],
    existing_end: Optional[str],
    new_start: Optional[str],
    new_end: Optional[str],
) -> bool:
    """
    Check if the new period is completely within the existing period.
    """
    norm_existing_start = normalize_date(existing_start)
    norm_existing_end = normalize_date(existing_end)
    norm_new_start = normalize_date(new_start)
    norm_new_end = normalize_date(new_end)

    # Handle None values
    far_future = "9999-12-31"
    far_past = "0001-01-01"

    norm_existing_start = norm_existing_start or far_past
    norm_existing_end = norm_existing_end or far_future
    norm_new_start = norm_new_start or far_past
    norm_new_end = norm_new_end or far_future

    # New period is subset if completely within existing period
    return norm_existing_start <= norm_new_start and norm_new_end <= norm_existing_end

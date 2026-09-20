"""Comparison of REST-shaped Wikidata statement documents.

Candidate statements extracted from sources are compared against existing
ones to decide whether they state a new fact, repeat a known fact, refine
it with more precision, or conflict with it. Only the tracked properties
are supported: P569/P570 (dates), P39 (position held), P19/P27 (place of
birth / country of citizenship).
"""

from enum import Enum

from .wikidata.date import WikidataDate
from .wikidata.document import (
    find_qualifiers,
    qualifier_time_value,
    statement_entity_id,
    statement_property_id,
    statement_time_value,
)


class StatementComparison(Enum):
    """Result of comparing a candidate statement against an existing one."""

    NO_MATCH = "no_match"
    """Unrelated statements: different property, or different entity QID."""

    EQUIVALENT = "equivalent"
    """Same fact at the same precision."""

    CANDIDATE_REFINES_EXISTING = "candidate_refines_existing"
    """Same fact, with the candidate strictly more precise."""

    EXISTING_SUBSUMES_CANDIDATE = "existing_subsumes_candidate"
    """Same fact, with the existing statement more precise."""

    INCOMPARABLE = "incomparable"
    """Same property (and same position QID for P39) but conflicting values."""


_DATE_PROPERTY_IDS = frozenset({"P569", "P570"})
_ENTITY_PROPERTY_IDS = frozenset({"P19", "P27"})
_POSITION_PROPERTY_ID = "P39"
_START_QUALIFIER_ID = "P580"
_END_QUALIFIER_ID = "P582"


def compare_statement(candidate: dict, existing: dict) -> StatementComparison:
    """Compare a candidate statement document against an existing one.

    Both are REST-shaped statements; the candidate is a create body, so it
    carries no id or rank.
    """
    property_id = statement_property_id(candidate)
    if property_id != statement_property_id(existing):
        return StatementComparison.NO_MATCH

    if property_id in _DATE_PROPERTY_IDS:
        return _compare_dates(candidate, existing)
    if property_id == _POSITION_PROPERTY_ID:
        return _compare_position(candidate, existing)
    if property_id in _ENTITY_PROPERTY_IDS:
        return _compare_entities(candidate, existing)

    raise ValueError(f"Unsupported property in statement comparison: {property_id}")


def is_timeframe_subsumed(existing_documents: list[dict], candidate: dict) -> bool:
    """Check whether consecutive existing position terms cover a candidate span.

    Detects when a source states a single span (e.g. "since 2021") that
    existing data already represents as multiple consecutive terms of the
    same position, making the candidate redundant.

    Only subsumes when:
    - at least 2 existing statements exist for the same position,
    - the candidate start could be some existing term's start,
    - the candidate is not more precise than that matched term, and
    - the candidate end matches the end of the consecutive chain built from
      that term, or both ends are open.
    """
    candidate_start, candidate_end = _extract_timeframe(candidate)
    if candidate_start is None:
        return False

    if len(existing_documents) < 2:
        return False

    existing_timeframes = sorted(
        (
            timeframe
            for timeframe in (
                _extract_timeframe(document) for document in existing_documents
            )
            if timeframe[0] is not None
        ),
        key=lambda timeframe: timeframe[0],
    )

    for i, (start, end) in enumerate(existing_timeframes):
        if not WikidataDate.dates_could_be_same(candidate_start, start):
            continue
        if WikidataDate.more_precise_date(candidate_start, start) == candidate_start:
            continue

        # Walk forward building a chain of consecutive terms
        chain_end = end
        for next_start, next_end in existing_timeframes[i + 1 :]:
            if chain_end is None or not chain_end.is_consecutive_with(next_start):
                break
            chain_end = next_end

        if candidate_end is None and chain_end is None:
            return True
        if (
            candidate_end is not None
            and chain_end is not None
            and WikidataDate.dates_could_be_same(candidate_end, chain_end)
            and WikidataDate.more_precise_date(candidate_end, chain_end)
            != candidate_end
        ):
            return True

    return False


def _compare_dates(candidate: dict, existing: dict) -> StatementComparison:
    """Compare two time-valued statements (P569/P570)."""
    candidate_date = statement_time_value(candidate)
    existing_date = statement_time_value(existing)

    if not WikidataDate.dates_could_be_same(candidate_date, existing_date):
        return StatementComparison.INCOMPARABLE

    more_precise = WikidataDate.more_precise_date(candidate_date, existing_date)
    if more_precise is None:
        return StatementComparison.EQUIVALENT
    if more_precise == candidate_date:
        return StatementComparison.CANDIDATE_REFINES_EXISTING
    return StatementComparison.EXISTING_SUBSUMES_CANDIDATE


def _compare_position(candidate: dict, existing: dict) -> StatementComparison:
    """Compare two position statements (P39) by entity and timeframe precision."""
    if statement_entity_id(candidate) != statement_entity_id(existing):
        return StatementComparison.NO_MATCH

    candidate_start, candidate_end = _extract_timeframe(candidate)
    existing_start, existing_end = _extract_timeframe(existing)

    # A statement with timeframe dates is more precise than one without. This
    # must be decided before dates_could_be_same, which never equates a date
    # with a missing date.
    candidate_has_dates = candidate_start is not None or candidate_end is not None
    existing_has_dates = existing_start is not None or existing_end is not None
    if candidate_has_dates and not existing_has_dates:
        return StatementComparison.CANDIDATE_REFINES_EXISTING
    if existing_has_dates and not candidate_has_dates:
        return StatementComparison.EXISTING_SUBSUMES_CANDIDATE

    if not (
        WikidataDate.dates_could_be_same(candidate_start, existing_start)
        and WikidataDate.dates_could_be_same(candidate_end, existing_end)
    ):
        return StatementComparison.INCOMPARABLE

    # Mixed precision: one side wins only if it is more precise on at least
    # one date and less precise on none; otherwise the statements are equal.
    start_more_precise = WikidataDate.more_precise_date(candidate_start, existing_start)
    end_more_precise = WikidataDate.more_precise_date(candidate_end, existing_end)

    candidate_refines = _refines(start_more_precise, candidate_start) or _refines(
        end_more_precise, candidate_end
    )
    existing_refines = _refines(start_more_precise, existing_start) or _refines(
        end_more_precise, existing_end
    )

    if candidate_refines and not existing_refines:
        return StatementComparison.CANDIDATE_REFINES_EXISTING
    if existing_refines and not candidate_refines:
        return StatementComparison.EXISTING_SUBSUMES_CANDIDATE
    return StatementComparison.EQUIVALENT


def _compare_entities(candidate: dict, existing: dict) -> StatementComparison:
    """Compare two entity-valued statements (P19/P27); same QID is the same fact."""
    if statement_entity_id(candidate) != statement_entity_id(existing):
        return StatementComparison.NO_MATCH
    return StatementComparison.EQUIVALENT


def _extract_timeframe(
    document: dict,
) -> tuple[WikidataDate | None, WikidataDate | None]:
    """Extract start (P580) and end (P582) dates from a statement's qualifiers."""
    return (
        _first_qualifier_time_value(document, _START_QUALIFIER_ID),
        _first_qualifier_time_value(document, _END_QUALIFIER_ID),
    )


def _first_qualifier_time_value(
    document: dict, property_id: str
) -> WikidataDate | None:
    """Time value of a statement's first qualifier for a property, if any.

    Statements without qualifiers omit the key (dump conversion and create
    bodies do), so a missing key means no qualifiers.
    """
    if "qualifiers" not in document:
        return None
    qualifiers = find_qualifiers(document, property_id)
    if not qualifiers:
        return None
    return qualifier_time_value(qualifiers[0])


def _refines(more_precise: WikidataDate | None, date: WikidataDate | None) -> bool:
    """Whether the date returned by more_precise_date is the given date."""
    return more_precise is not None and more_precise == date

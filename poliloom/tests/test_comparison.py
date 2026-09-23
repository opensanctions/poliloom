"""Tests for statement comparison on REST-shaped statement documents."""

import pytest

from poliloom.comparison import (
    StatementComparison,
    compare_statement,
    is_timeframe_subsumed,
)
from poliloom.wikidata.date import WikidataDate


def date_statement(property_id: str, date_string: str) -> dict:
    """A time-valued create-body statement (e.g. date of birth)."""
    return {
        "property": {"id": property_id},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(
                date_string
            ).to_rest_time_content(),
        },
    }


def entity_statement(property_id: str, entity_id: str) -> dict:
    """An entity-valued create-body statement (e.g. place of birth)."""
    return {
        "property": {"id": property_id},
        "value": {"type": "value", "content": entity_id},
    }


def position_statement(
    entity_id: str, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """A position statement pointing at an entity, with optional timeframe."""
    statement = entity_statement("P39", entity_id)
    qualifiers = []
    if start_date:
        qualifiers.append(time_qualifier("P580", start_date))
    if end_date:
        qualifiers.append(time_qualifier("P582", end_date))
    if qualifiers:
        statement["qualifiers"] = qualifiers
    return statement


def time_qualifier(property_id: str, date_string: str) -> dict:
    """A time-valued qualifier (e.g. start time)."""
    return {
        "property": {"id": property_id},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(
                date_string
            ).to_rest_time_content(),
        },
    }


class TestCompareStatement:
    """Tests for compare_statement()."""

    def test_different_properties_no_match(self):
        """Statements on different properties are unrelated."""
        candidate = date_statement("P569", "1950-05-15")
        existing = date_statement("P570", "1950-05-15")

        assert compare_statement(candidate, existing) is StatementComparison.NO_MATCH

    def test_date_equal_precision(self):
        """Dates at the same precision stating the same time are equivalent."""
        candidate = date_statement("P569", "1950-05-15")
        existing = date_statement("P569", "1950-05-15")

        assert compare_statement(candidate, existing) is StatementComparison.EQUIVALENT

    def test_date_candidate_more_precise(self):
        """A day-precision date refines a month-precision date."""
        candidate = date_statement("P569", "1950-05-15")
        existing = date_statement("P569", "1950-05")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.CANDIDATE_REFINES_EXISTING

    def test_date_existing_more_precise(self):
        """A year-precision date is subsumed by a day-precision date."""
        candidate = date_statement("P569", "1950")
        existing = date_statement("P569", "1950-05-15")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.EXISTING_SUBSUMES_CANDIDATE

    def test_date_different_years_incomparable(self):
        """Dates that could not be the same conflict."""
        candidate = date_statement("P569", "1950-05-15")
        existing = date_statement("P569", "1951-05-15")

        assert (
            compare_statement(candidate, existing) is StatementComparison.INCOMPARABLE
        )

    def test_position_different_entity_no_match(self):
        """Positions held at different entities are unrelated."""
        candidate = position_statement("Q123")
        existing = position_statement("Q456")

        assert compare_statement(candidate, existing) is StatementComparison.NO_MATCH

    def test_position_candidate_has_dates_existing_none(self):
        """A position with timeframe dates refines one without."""
        candidate = position_statement("Q123", start_date="2020-01-01")
        existing = position_statement("Q123")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.CANDIDATE_REFINES_EXISTING

    def test_position_existing_has_dates_candidate_none(self):
        """A position without timeframe dates is subsumed by one with them."""
        candidate = position_statement("Q123")
        existing = position_statement("Q123", start_date="2020-01-01")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.EXISTING_SUBSUMES_CANDIDATE

    def test_position_both_no_dates_equal(self):
        """Positions without timeframe dates are equivalent."""
        candidate = position_statement("Q123")
        existing = position_statement("Q123")

        assert compare_statement(candidate, existing) is StatementComparison.EQUIVALENT

    def test_position_candidate_dates_more_precise(self):
        """A more precise start date refines a year-precision timeframe."""
        candidate = position_statement("Q123", start_date="2020-06-15")
        existing = position_statement("Q123", start_date="2020")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.CANDIDATE_REFINES_EXISTING

    def test_position_mixed_precision_equal(self):
        """More precision on the start and less on the end balances out."""
        candidate = position_statement("Q123", "2020-06-15", "2021")
        existing = position_statement("Q123", "2020", "2021-03-31")

        result = compare_statement(candidate, existing)

        assert result is StatementComparison.EQUIVALENT

    def test_position_different_timeframes_incomparable(self):
        """Positions with different starts conflict."""
        candidate = position_statement("Q123", start_date="2020-01-01")
        existing = position_statement("Q123", start_date="2015-01-01")

        assert (
            compare_statement(candidate, existing) is StatementComparison.INCOMPARABLE
        )

    def test_birthplace_same_entity_equal(self):
        """Birthplaces pointing at the same entity are equivalent."""
        candidate = entity_statement("P19", "Q60")
        existing = entity_statement("P19", "Q60")

        assert compare_statement(candidate, existing) is StatementComparison.EQUIVALENT

    def test_birthplace_different_entity_no_match(self):
        """Birthplaces pointing at different entities are unrelated."""
        candidate = entity_statement("P19", "Q60")
        existing = entity_statement("P19", "Q65")

        assert compare_statement(candidate, existing) is StatementComparison.NO_MATCH

    def test_citizenship_same_entity_equal(self):
        """Citizenships pointing at the same entity are equivalent."""
        candidate = entity_statement("P27", "Q30")
        existing = entity_statement("P27", "Q30")

        assert compare_statement(candidate, existing) is StatementComparison.EQUIVALENT

    def test_unsupported_property_raises(self):
        """Only the tracked properties are comparable."""
        candidate = entity_statement("P106", "Q82955")
        existing = entity_statement("P106", "Q82955")

        with pytest.raises(ValueError, match="P106"):
            compare_statement(candidate, existing)


class TestTimeframeSubsumption:
    """Tests for is_timeframe_subsumed()."""

    def test_two_consecutive_terms_subsume_single_span(self):
        existing = [
            position_statement("Q123", "2021-03-31", "2023-10-26"),
            position_statement("Q123", start_date="2023-10-27"),
        ]
        assert is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2021-03-31")
        )

    def test_end_date_mismatch_not_subsumed(self):
        existing = [
            position_statement("Q123", "2021-03-31", "2022-12-31"),
            position_statement("Q123", "2024-01-01", "2024-12-31"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2021-03-31")
        )

    def test_candidate_start_no_match_not_subsumed(self):
        existing = [
            position_statement("Q123", "2022-01-01", "2023-06-30"),
            position_statement("Q123", start_date="2023-07-01"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2020-01-01")
        )

    def test_gap_between_terms_not_subsumed(self):
        existing = [
            position_statement("Q123", "2015-01-01", "2017-12-31"),
            position_statement("Q123", start_date="2021-01-01"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2015-01-01")
        )

    def test_single_existing_term_not_subsumed(self):
        existing = [position_statement("Q123", start_date="2021-03-31")]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2021-03-31")
        )

    def test_candidate_no_start_date_not_subsumed(self):
        existing = [
            position_statement("Q123", "2021-03-31", "2023-10-26"),
            position_statement("Q123", start_date="2023-10-27"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", end_date="2023-10-26")
        )

    def test_candidate_no_dates_not_subsumed(self):
        existing = [
            position_statement("Q123", "2021-03-31", "2023-10-26"),
            position_statement("Q123", start_date="2023-10-27"),
        ]
        assert not is_timeframe_subsumed(existing, position_statement("Q123"))

    def test_candidate_more_precise_not_subsumed(self):
        existing = [
            position_statement("Q123", start_date="2021"),
            position_statement("Q123", start_date="2022"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", "2021-06-15", "2022-12-01")
        )

    def test_candidate_less_precise_subsumed(self):
        existing = [
            position_statement("Q123", "2021-03-31", "2023-10-26"),
            position_statement("Q123", start_date="2023-10-27"),
        ]
        assert is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2021")
        )

    def test_three_consecutive_terms_subsume(self):
        existing = [
            position_statement("Q123", "2015-01-01", "2018-12-31"),
            position_statement("Q123", "2019-01-01", "2022-12-31"),
            position_statement("Q123", start_date="2023-01-01"),
        ]
        assert is_timeframe_subsumed(
            existing, position_statement("Q123", start_date="2015-01-01")
        )

    def test_mid_chain_open_end_breaks_chain(self):
        """A term with no end date in the middle of the chain stops the walk."""
        existing = [
            position_statement("Q123", start_date="2015-01-01"),
            position_statement("Q123", "2019-01-01", "2022-12-31"),
        ]
        assert not is_timeframe_subsumed(
            existing, position_statement("Q123", "2015-01-01", "2022-12-31")
        )

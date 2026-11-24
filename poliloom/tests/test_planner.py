"""Tests for the enrichment decision core."""

from copy import deepcopy

import pytest

from poliloom.payloads import (
    append_qualifier_patch,
    create_body,
    refine_qualifier_patch,
    refine_value_patch,
)
from poliloom.planner import Decision, plan
from poliloom.wikidata.date import WikidataDate


def decision_create_statement(candidate: dict) -> dict:
    """The candidate as it appears in a create body."""
    statement = dict(candidate)
    statement["references"] = []
    statement.setdefault("rank", "normal")
    return statement


def date_statement(property_id: str, date_string: str) -> dict:
    """A time-valued candidate (e.g. date of birth)."""
    return {
        "property": {"id": property_id},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(
                date_string
            ).to_rest_time_content(),
        },
        "qualifiers": [],
    }


def entity_statement(property_id: str, entity_id: str) -> dict:
    """An entity-valued candidate (e.g. place of birth)."""
    return {
        "property": {"id": property_id},
        "value": {"type": "value", "content": entity_id},
        "qualifiers": [],
    }


def time_qualifier(property_id: str, date_string: str) -> dict:
    return {
        "property": {"id": property_id, "data_type": "time"},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(
                date_string
            ).to_rest_time_content(),
        },
    }


def position_statement(
    entity_id: str, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """A position candidate with an optional timeframe."""
    statement = entity_statement("P39", entity_id)
    qualifiers = []
    if start_date:
        qualifiers.append(time_qualifier("P580", start_date))
    if end_date:
        qualifiers.append(time_qualifier("P582", end_date))
    statement["qualifiers"] = qualifiers
    return statement


def as_document(
    statement: dict, references: list[dict] | None = None, suffix: str = "0000"
) -> dict:
    """A cached statement document (REST shape with id and rank)."""
    return {
        "id": f"Q42${suffix}-4cc1-8d1e-1a1f-2f3f4f5f6f7f",
        "rank": "normal",
        **deepcopy(statement),
        "references": references or [],
    }


def supported_statement(document: dict) -> Decision:
    return Decision(
        "edit",
        {
            "patch": [
                {"op": "test", "path": "/value", "value": document["value"]},
                {"op": "test", "path": "/qualifiers", "value": document["qualifiers"]},
            ]
        },
        0,
    )


class TestPlanDates:
    """P569/P570 rules."""

    def test_candidate_refines_value(self):
        candidate = date_statement("P569", "1950-05-15")
        document = as_document(date_statement("P569", "1950"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit", refine_value_patch(document, candidate["value"]), 0
        )

    def test_target_index_points_into_property_filtered_list(self):
        candidate = date_statement("P569", "1950-05-15")
        documents = [
            as_document(entity_statement("P19", "Q60")),
            as_document(date_statement("P569", "1950")),
            as_document(position_statement("Q123")),
        ]

        decision = plan(candidate, documents)

        assert decision is not None
        assert decision.target_index == 0

    def test_equivalent_supports_existing_statement_regardless_of_references(self):
        candidate = date_statement("P570", "1990-06-15")
        document = as_document(
            candidate,
            references=[
                {
                    "parts": [
                        {
                            "property": {"id": "P854"},
                            "value": {
                                "type": "value",
                                "content": "https://example.org/biography",
                            },
                        }
                    ]
                }
            ],
        )

        assert plan(candidate, [document]) == supported_statement(document)

    def test_existing_subsumes_candidate(self):
        candidate = date_statement("P569", "1950")
        document = as_document(date_statement("P569", "1950-05-15"))

        assert plan(candidate, [document]) == supported_statement(document)

    def test_conflicting_date_creates(self):
        candidate = date_statement("P569", "1950-05-15")
        documents = [as_document(date_statement("P569", "1951-05-15"))]

        decision = plan(candidate, documents)

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_compatible_targets_create(self):
        candidate = date_statement("P569", "1950-05-15")
        documents = [
            as_document(date_statement("P569", "1950")),
            as_document(date_statement("P569", "1950-05")),
        ]

        decision = plan(candidate, documents)

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )


class TestPlanPositions:
    """P39 rules."""

    def test_appends_missing_start_qualifier(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P580", "2020-01-01")),
            0,
        )

    def test_appends_missing_end_qualifier(self):
        candidate = position_statement("Q123", end_date="2021-06-30")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P582", "2021-06-30")),
            0,
        )

    def test_p580_appended_before_p582(self):
        """When both timeframe qualifiers are missing, P580 goes first."""
        candidate = position_statement("Q123", "2020-01-01", "2021-06-30")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P580", "2020-01-01")),
            0,
        )

    def test_refines_more_precise_qualifier_in_place(self):
        """The replaced qualifier is targeted at its own index in the document."""
        candidate = position_statement("Q123", "2020-06-15", "2021")
        document = as_document(position_statement("Q123", "2020", "2021"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit",
            refine_qualifier_patch(document, 0, time_qualifier("P580", "2020-06-15")),
            0,
        )

    def test_refinement_targets_qualifier_at_its_document_index(self):
        """P580 sitting after P582 is replaced at index 1, not index 0."""
        candidate = position_statement("Q123", "2020-06-15", "2021")
        document = as_document(position_statement("Q123"))
        document["qualifiers"] = [
            time_qualifier("P582", "2021"),
            time_qualifier("P580", "2020"),
        ]

        decision = plan(candidate, [document])

        assert decision == Decision(
            "edit",
            refine_qualifier_patch(document, 1, time_qualifier("P580", "2020-06-15")),
            0,
        )

    def test_equivalent_supports_existing_statement(self):
        candidate = position_statement("Q123")
        document = as_document(candidate)

        assert plan(candidate, [document]) == supported_statement(document)

    def test_existing_subsumes_candidate(self):
        candidate = position_statement("Q123")
        document = as_document(position_statement("Q123", start_date="2020-01-01"))

        assert plan(candidate, [document]) == supported_statement(document)

    def test_open_ended_candidate_supports_matching_closed_term(self):
        candidate = position_statement("Q123", start_date="1998-08-25")
        document = as_document(position_statement("Q123", "1998-08-25", "2002-05-22"))

        assert plan(candidate, [document]) == supported_statement(document)

    def test_incompatible_timeframe_creates(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q123", start_date="2015-01-01"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_other_position_creates(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q456", start_date="2020-01-01"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_compatible_targets_create(self):
        candidate = position_statement("Q123")
        documents = [
            as_document(position_statement("Q123")),
            as_document(position_statement("Q123")),
        ]

        decision = plan(candidate, documents)

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_subsumed_span_does_nothing(self):
        """A span covered by consecutive existing terms is not recreated."""
        candidate = position_statement("Q123", start_date="2021-03-31")
        documents = [
            as_document(position_statement("Q123", "2021-03-31", "2023-10-26")),
            as_document(position_statement("Q123", start_date="2023-10-27")),
        ]

        assert plan(candidate, documents) is None

    def test_subsumed_span_supports_unique_equivalent_target(self):
        candidate = position_statement("Q123", start_date="2021")
        open_ended = as_document(position_statement("Q123", start_date="2021"))
        later_term = as_document(position_statement("Q123", "2022", "2023-12-31"))

        assert plan(candidate, [open_ended, later_term]) == supported_statement(
            open_ended
        )

    def test_subsumed_span_with_multiple_equivalent_targets_does_nothing(self):
        candidate = position_statement("Q123", start_date="2021")
        documents = [
            as_document(position_statement("Q123", start_date="2021")),
            as_document(position_statement("Q123", start_date="2021")),
            as_document(position_statement("Q123", "2022", "2023-12-31")),
        ]

        assert plan(candidate, documents) is None


class TestPlanEntities:
    """P19/P27 rules."""

    def test_equivalent_supports_existing_statement(self):
        candidate = entity_statement("P19", "Q60")
        document = as_document(candidate)

        assert plan(candidate, [document]) == supported_statement(document)

    def test_different_entity_creates_never_replaces(self):
        candidate = entity_statement("P19", "Q65")
        document = as_document(entity_statement("P19", "Q60"))

        decision = plan(candidate, [document])

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_equivalent_targets_create(self):
        candidate = entity_statement("P27", "Q30")
        documents = [
            as_document(entity_statement("P27", "Q30")),
            as_document(entity_statement("P27", "Q30")),
        ]

        decision = plan(candidate, documents)

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )


class TestCreatePayload:
    """Shape of the create body built by plan()."""

    def test_date_create_includes_rank_but_no_source_reference(self):
        candidate = date_statement("P569", "1950-05-15")

        decision = plan(candidate, [])

        statement = decision.payload["statement"]
        assert statement["references"] == []
        assert statement["rank"] == "normal"
        assert statement["value"] == candidate["value"]
        assert decision.target_index is None

    def test_position_create_carries_qualifiers(self):
        candidate = position_statement("Q123", "2020-01-01", "2021-06-30")

        decision = plan(candidate, [])

        statement = decision.payload["statement"]
        assert statement["qualifiers"] == candidate["qualifiers"]
        assert statement["value"] == candidate["value"]

    def test_candidate_dict_not_mutated(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        snapshot = deepcopy(candidate)

        plan(candidate, [])

        assert candidate == snapshot


class TestUnsupportedProperty:
    def test_unsupported_property_raises(self):
        candidate = entity_statement("P106", "Q82955")

        with pytest.raises(ValueError, match="P106"):
            plan(candidate, [])

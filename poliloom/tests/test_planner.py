"""Tests for the enrichment decision core."""

from copy import deepcopy

import pytest

from poliloom.payloads import (
    append_qualifier_patch,
    append_reference_patch,
    create_body,
    refine_qualifier_patch,
    refine_value_patch,
)
from poliloom.planner import (
    Decision,
    plan,
    reference_identity,
    reference_present,
)
from poliloom.wikidata.date import WikidataDate

SOURCE_URL = "https://example.org/biography"
IMPORT_URL = "https://en.wikipedia.org/w/index.php?oldid=12345"


def url_part(url: str, property_id: str = "P854") -> dict:
    return {
        "property": {"id": property_id, "data_type": "url"},
        "value": {"type": "value", "content": url},
    }


def url_reference(url: str = SOURCE_URL, hash: str | None = None) -> dict:
    """A proposed reference with a P854 part; documents add a read-only hash."""
    reference = {"parts": [url_part(url)]}
    if hash is not None:
        reference["hash"] = hash
    return reference


def import_reference(hash: str | None = None) -> dict:
    """A proposed Wikipedia reference identified by its P4656 import URL."""
    reference = {"parts": [url_part(IMPORT_URL, "P4656")]}
    if hash is not None:
        reference["hash"] = hash
    return reference


def retrieved_part() -> dict:
    return {
        "property": {"id": "P813", "data_type": "time"},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(
                "2024-01-15"
            ).to_rest_time_content(),
        },
    }


def proposed_reference() -> dict:
    """The reference plan() is asked to attach, as built for evidence sources."""
    return {"parts": [url_part(SOURCE_URL), retrieved_part()]}


def decision_create_statement(candidate: dict) -> dict:
    """The candidate as it appears in a create body: referenced and ranked."""
    statement = dict(candidate)
    statement["references"] = [proposed_reference()]
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
    }


def entity_statement(property_id: str, entity_id: str) -> dict:
    """An entity-valued candidate (e.g. place of birth)."""
    return {
        "property": {"id": property_id},
        "value": {"type": "value", "content": entity_id},
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
    if qualifiers:
        statement["qualifiers"] = qualifiers
    return statement


def as_document(
    statement: dict, references: list[dict] | None = None, suffix: str = "0000"
) -> dict:
    """A cached statement document (REST shape with id and rank)."""
    document = {
        "id": f"Q42${suffix}-4cc1-8d1e-1a1f-2f3f4f5f6f7f",
        "rank": "normal",
        **deepcopy(statement),
    }
    if references is not None:
        document["references"] = references
    return document


def with_reference(statement: dict, reference: dict) -> dict:
    """A candidate already carrying the proposed reference on the document."""
    return as_document(statement, references=[reference, url_reference()])


class TestReferenceIdentity:
    """Tests for reference_identity()."""

    def test_p854_url_identifies(self):
        assert reference_identity(url_reference()) == SOURCE_URL

    def test_p4656_import_url_identifies_when_no_p854(self):
        assert reference_identity(import_reference()) == IMPORT_URL

    def test_p854_wins_over_p4656(self):
        reference = {"parts": [url_part(IMPORT_URL, "P4656"), url_part(SOURCE_URL)]}

        assert reference_identity(reference) == SOURCE_URL

    def test_parts_only_identity_is_canonical_json(self):
        imported_from = {
            "property": {"id": "P143", "data_type": "wikibase-item"},
            "value": {"type": "value", "content": "Q328"},
        }
        reference = {"parts": [imported_from]}

        assert reference_identity(reference) == reference_identity(
            {"parts": [deepcopy(imported_from)]}
        )
        assert reference_identity(reference) != reference_identity(
            {
                "parts": [
                    {
                        "property": {"id": "P143"},
                        "value": {"type": "value", "content": "Q52"},
                    }
                ]
            }
        )

    def test_p813_never_affects_identity(self):
        without = url_reference()
        with_date = {"parts": [url_part(SOURCE_URL), retrieved_part()]}

        assert reference_identity(without) == reference_identity(with_date)

    def test_hash_ignored(self):
        document_reference = url_reference(hash="1" * 40)

        assert reference_identity(document_reference) == reference_identity(
            url_reference()
        )


class TestReferencePresent:
    """Tests for reference_present()."""

    def test_missing_references_key_means_none(self):
        assert not reference_present(
            as_document(date_statement("P569", "1950")), url_reference()
        )

    def test_matching_reference_present(self):
        document = as_document(
            date_statement("P569", "1950"), references=[url_reference(hash="1" * 40)]
        )

        assert reference_present(document, url_reference())

    def test_other_reference_not_present(self):
        document = as_document(
            date_statement("P569", "1950"),
            references=[url_reference("https://elsewhere.org")],
        )

        assert not reference_present(document, url_reference())

    def test_import_url_reference_matched_without_hash_or_retrieval(self):
        """A stored Wikipedia reference matches the proposed one despite
        read-only and retrieval-date differences."""
        document = as_document(
            position_statement("Q123"),
            references=[
                {
                    "hash": "2" * 40,
                    "parts": [url_part(IMPORT_URL, "P4656"), retrieved_part()],
                }
            ],
        )

        assert reference_present(document, import_reference())


class TestPlanDates:
    """P569/P570 rules."""

    def test_candidate_refines_value(self):
        candidate = date_statement("P569", "1950-05-15")
        document = as_document(date_statement("P569", "1950"))

        decision = plan(candidate, [document], proposed_reference())

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

        decision = plan(candidate, documents, proposed_reference())

        assert decision is not None
        assert decision.target_index == 0

    def test_equivalent_appends_missing_reference(self):
        candidate = date_statement("P570", "1990-06-15")
        document = as_document(date_statement("P570", "1990-06-15"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(document, proposed_reference()), 0
        )

    def test_equivalent_with_reference_present_does_nothing(self):
        candidate = date_statement("P570", "1990-06-15")
        document = with_reference(date_statement("P570", "1990-06-15"), url_reference())

        assert plan(candidate, [document], proposed_reference()) is None

    def test_existing_subsumes_candidate_appends_missing_reference(self):
        candidate = date_statement("P569", "1950")
        document = as_document(date_statement("P569", "1950-05-15"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(document, proposed_reference()), 0
        )

    def test_conflicting_date_creates(self):
        candidate = date_statement("P569", "1950-05-15")
        documents = [as_document(date_statement("P569", "1951-05-15"))]

        decision = plan(candidate, documents, proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_compatible_targets_create(self):
        candidate = date_statement("P569", "1950-05-15")
        documents = [
            as_document(date_statement("P569", "1950")),
            as_document(date_statement("P569", "1950-05")),
        ]

        decision = plan(candidate, documents, proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )


class TestPlanPositions:
    """P39 rules."""

    def test_appends_missing_start_qualifier(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P580", "2020-01-01")),
            0,
        )

    def test_appends_missing_end_qualifier(self):
        candidate = position_statement("Q123", end_date="2021-06-30")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P582", "2021-06-30")),
            0,
        )

    def test_p580_appended_before_p582(self):
        """When both timeframe qualifiers are missing, P580 goes first."""
        candidate = position_statement("Q123", "2020-01-01", "2021-06-30")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit",
            append_qualifier_patch(document, time_qualifier("P580", "2020-01-01")),
            0,
        )

    def test_refines_more_precise_qualifier_in_place(self):
        """The replaced qualifier is targeted at its own index in the document."""
        candidate = position_statement("Q123", "2020-06-15", "2021")
        document = as_document(position_statement("Q123", "2020", "2021"))

        decision = plan(candidate, [document], proposed_reference())

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

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit",
            refine_qualifier_patch(document, 1, time_qualifier("P580", "2020-06-15")),
            0,
        )

    def test_equivalent_appends_missing_reference(self):
        candidate = position_statement("Q123")
        document = as_document(position_statement("Q123"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(document, proposed_reference()), 0
        )

    def test_equivalent_with_reference_present_does_nothing(self):
        candidate = position_statement("Q123")
        document = with_reference(position_statement("Q123"), url_reference())

        assert plan(candidate, [document], proposed_reference()) is None

    def test_existing_subsumes_candidate_appends_missing_reference(self):
        candidate = position_statement("Q123")
        document = as_document(position_statement("Q123", start_date="2020-01-01"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(document, proposed_reference()), 0
        )

    def test_incompatible_timeframe_creates(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q123", start_date="2015-01-01"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_other_position_creates(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        document = as_document(position_statement("Q456", start_date="2020-01-01"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_compatible_targets_create(self):
        candidate = position_statement("Q123")
        documents = [
            as_document(position_statement("Q123")),
            as_document(position_statement("Q123")),
        ]

        decision = plan(candidate, documents, proposed_reference())

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

        assert plan(candidate, documents, proposed_reference()) is None

    def test_subsumed_span_with_unique_equivalent_target_appends_reference(self):
        candidate = position_statement("Q123", start_date="2021")
        open_ended = as_document(position_statement("Q123", start_date="2021"))
        later_term = as_document(position_statement("Q123", "2022", "2023-12-31"))

        decision = plan(candidate, [open_ended, later_term], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(open_ended, proposed_reference()), 0
        )

    def test_subsumed_span_with_reference_present_does_nothing(self):
        candidate = position_statement("Q123", start_date="2021")
        open_ended = with_reference(
            position_statement("Q123", start_date="2021"), url_reference()
        )
        later_term = as_document(position_statement("Q123", "2022", "2023-12-31"))

        assert plan(candidate, [open_ended, later_term], proposed_reference()) is None

    def test_subsumed_span_with_multiple_equivalent_targets_does_nothing(self):
        candidate = position_statement("Q123", start_date="2021")
        documents = [
            as_document(position_statement("Q123", start_date="2021")),
            as_document(position_statement("Q123", start_date="2021")),
            as_document(position_statement("Q123", "2022", "2023-12-31")),
        ]

        assert plan(candidate, documents, proposed_reference()) is None


class TestPlanEntities:
    """P19/P27 rules."""

    def test_equivalent_appends_missing_reference(self):
        candidate = entity_statement("P19", "Q60")
        document = as_document(entity_statement("P19", "Q60"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "edit", append_reference_patch(document, proposed_reference()), 0
        )

    def test_equivalent_with_reference_present_does_nothing(self):
        candidate = entity_statement("P27", "Q30")
        document = with_reference(entity_statement("P27", "Q30"), url_reference())

        assert plan(candidate, [document], proposed_reference()) is None

    def test_different_entity_creates_never_replaces(self):
        candidate = entity_statement("P19", "Q65")
        document = as_document(entity_statement("P19", "Q60"))

        decision = plan(candidate, [document], proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )

    def test_multiple_equivalent_targets_create(self):
        candidate = entity_statement("P27", "Q30")
        documents = [
            as_document(entity_statement("P27", "Q30")),
            as_document(entity_statement("P27", "Q30")),
        ]

        decision = plan(candidate, documents, proposed_reference())

        assert decision == Decision(
            "create", create_body(decision_create_statement(candidate))
        )


class TestCreatePayload:
    """Shape of the create body built by plan()."""

    def test_date_create_includes_reference_and_rank(self):
        candidate = date_statement("P569", "1950-05-15")

        decision = plan(candidate, [], proposed_reference())

        statement = decision.payload["statement"]
        assert statement["references"] == [proposed_reference()]
        assert statement["rank"] == "normal"
        assert statement["value"] == candidate["value"]
        assert decision.target_index is None

    def test_position_create_carries_qualifiers(self):
        candidate = position_statement("Q123", "2020-01-01", "2021-06-30")

        decision = plan(candidate, [], proposed_reference())

        statement = decision.payload["statement"]
        assert statement["qualifiers"] == candidate["qualifiers"]
        assert statement["value"] == candidate["value"]

    def test_candidate_dict_not_mutated(self):
        candidate = position_statement("Q123", start_date="2020-01-01")
        snapshot = deepcopy(candidate)

        plan(candidate, [], proposed_reference())

        assert candidate == snapshot


class TestUnsupportedProperty:
    def test_unsupported_property_raises(self):
        candidate = entity_statement("P106", "Q82955")

        with pytest.raises(ValueError, match="P106"):
            plan(candidate, [], proposed_reference())

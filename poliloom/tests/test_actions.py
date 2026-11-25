"""Tests for creating review actions against cached statement facts."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from poliloom.actions import create_action
from poliloom.models import Politician, Source, Statement
from poliloom.proposals import statement_fact
from poliloom.wikidata.date import WikidataDate


def time_value(date):
    return {
        "type": "value",
        "content": WikidataDate.from_date_string(date).to_rest_time_content(),
    }


def date_fact(date, prop="P569"):
    return {"property": {"id": prop}, "value": time_value(date), "qualifiers": []}


def entity_fact(prop, qid):
    return {
        "property": {"id": prop},
        "value": {"type": "value", "content": qid},
        "qualifiers": [],
    }


def position(qid="Q123", start=None, end=None):
    return {
        **entity_fact("P39", qid),
        "qualifiers": [
            {"property": {"id": prop}, "value": time_value(date)}
            for prop, date in [("P580", start), ("P582", end)]
            if date
        ],
    }


def document(fact, statement_id="Q42$deadbeef"):
    return {
        **deepcopy(fact),
        "id": statement_id,
        "rank": "normal",
        "references": [
            {
                "hash": "existing",
                "parts": [
                    {
                        "property": {"id": "P854"},
                        "value": {"type": "value", "content": "https://example.org"},
                    },
                ],
            }
        ],
    }


def create_from_documents(candidate, documents):
    politician = Politician(id=uuid4(), wikidata_id="Q42")
    statements = [
        Statement(
            politician_id=politician.id,
            document=document,
            wikidata_statement_id=document["id"],
        )
        for document in documents
    ]
    source = Source(url="https://example.com/source", fetch_timestamp=datetime.now(UTC))
    return create_action(politician, candidate, statements, source, [])


def create(candidate, existing):
    return create_from_documents(candidate, list(map(document, existing)))


@pytest.mark.parametrize(
    ("candidate", "existing"),
    [
        (date_fact("1950-05-15"), []),
        (date_fact("1950-05-15"), [date_fact("1951-05-15")]),
        (date_fact("1950-05-15"), [date_fact("1950"), date_fact("1950-05")]),
        (position(start="2020-01-01", end="2021-06-30"), []),
        (position(start="2020-01-01"), [position(start="2015-01-01")]),
        (position("Q123"), [position("Q456")]),
        (position(), [position(), position()]),
        (entity_fact("P19", "Q65"), [entity_fact("P19", "Q60")]),
        (
            entity_fact("P27", "Q30"),
            [entity_fact("P27", "Q30"), entity_fact("P27", "Q30")],
        ),
    ],
)
def test_add_is_the_extracted_fact_without_statement_metadata(candidate, existing):
    extraction = document(candidate)
    original = deepcopy(extraction)

    action = create(extraction, existing)

    assert action.before is None
    assert action.target_wikidata_statement_id is None
    assert action.after == candidate
    assert extraction == original


@pytest.mark.parametrize(
    ("candidate", "existing"),
    [
        (date_fact("1990-06-15", "P570"), date_fact("1990-06-15", "P570")),
        (date_fact("1950"), date_fact("1950-05-15")),
        (position(), position()),
        (position(), position(start="2020-01-01")),
        (position(start="1998-08-25"), position(start="1998-08-25", end="2002-05-22")),
        (entity_fact("P19", "Q60"), entity_fact("P19", "Q60")),
    ],
)
def test_citation_freezes_existing_fact_even_if_the_extraction_is_less_precise(
    candidate, existing
):
    action = create(candidate, [existing])

    assert action.before == existing
    assert action.after == existing
    assert action.target_wikidata_statement_id == "Q42$deadbeef"


def test_date_refinement_targets_the_matching_cached_statement():
    candidate = date_fact("1950-05-15")
    before = date_fact("1950")
    before["qualifiers"] = [
        {"property": {"id": "P1480"}, "value": {"type": "value", "content": "Q5727902"}}
    ]
    documents = [
        document(entity_fact("P19", "Q60"), "Q42$birthplace"),
        document(before, "Q42$birth"),
        document(position(), "Q42$position"),
    ]

    action = create_from_documents(candidate, documents)

    assert action.before == before
    assert action.after == {**before, "value": candidate["value"]}
    assert action.target_wikidata_statement_id == "Q42$birth"


@pytest.mark.parametrize(
    ("start", "end", "expected_start", "expected_end"),
    [
        ("2020-01-01", None, "2020-01-01", None),
        (None, "2021-06-30", None, "2021-06-30"),
        ("2020-01-01", "2021-06-30", "2020-01-01", None),
    ],
)
def test_appends_only_one_missing_qualifier_start_first(
    start, end, expected_start, expected_end
):
    before = position()

    action = create(position(start=start, end=end), [before])

    assert action.before == before
    assert action.after == position(start=expected_start, end=expected_end)
    assert action.target_wikidata_statement_id == "Q42$deadbeef"


def test_start_only_refinement_preserves_known_end_and_other_qualifier_values():
    designation = {
        "property": {"id": "P1545"},
        "value": {"type": "value", "content": "1"},
    }
    before = position(start="2020", end="2021")
    start, end = before["qualifiers"]
    before["qualifiers"] = [end, designation, start, designation]
    cached = document(before)
    candidate = position(start="2020-06-15")
    expected_after = {
        **before,
        "qualifiers": [end, designation, candidate["qualifiers"][0], designation],
    }

    action = create(candidate, [before])

    assert action.before == before
    assert action.after == expected_after
    assert action.target_wikidata_statement_id == "Q42$deadbeef"
    assert statement_fact(cached) == before


def test_subsumed_span_does_nothing():
    assert (
        create(
            position(start="2021-03-31"),
            [
                position(start="2021-03-31", end="2023-10-26"),
                position(start="2023-10-27"),
            ],
        )
        is None
    )


def test_subsumed_span_supports_unique_equivalent_target():
    candidate = position(start="2021")
    other = position(start="2022", end="2023-12-31")

    action = create(candidate, [candidate, other])

    assert action.before == candidate
    assert action.after == candidate
    assert action.target_wikidata_statement_id == "Q42$deadbeef"
    assert create(candidate, [candidate, other, candidate]) is None


def test_unsupported_property_raises():
    with pytest.raises(ValueError, match="P106"):
        create(entity_fact("P106", "Q82955"), [])

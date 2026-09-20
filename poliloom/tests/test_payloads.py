"""Tests for Action payload builders."""

from copy import deepcopy

from poliloom.payloads import (
    append_qualifier_patch,
    append_reference_patch,
    create_body,
    refine_qualifier_patch,
    refine_value_patch,
)

_TIME = {
    "time": "+2020-01-01T00:00:00Z",
    "precision": 9,
    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
}

_START_TIME_QUALIFIER = {
    "property": {"id": "P580", "data_type": "time"},
    "value": {"type": "value", "content": _TIME},
}

_END_TIME_QUALIFIER = {
    "property": {"id": "P582", "data_type": "time"},
    "value": {"type": "value", "content": dict(_TIME, time="+2024-06-30T00:00:00Z")},
}

_URL_REFERENCE = {
    "hash": "1" * 40,
    "parts": [
        {
            "property": {"id": "P854", "data_type": "url"},
            "value": {"type": "value", "content": "https://example.org/source"},
        }
    ],
}


def _statement() -> dict:
    """P39 statement without qualifiers or references (import shape)."""
    return {
        "id": "Q42$7b80d2d0-4cc1-8d1e-1a1f-2f3f4f5f6f7f",
        "rank": "normal",
        "property": {"id": "P39", "data_type": "wikibase-item"},
        "value": {"type": "value", "content": "Q11696"},
    }


def _full_statement() -> dict:
    """P39 statement with qualifiers and references (Wikidata REST shape)."""
    statement = _statement()
    statement["qualifiers"] = [_START_TIME_QUALIFIER, _END_TIME_QUALIFIER]
    statement["references"] = [_URL_REFERENCE]
    return statement


def test_create_body_wraps_bare_statement():
    statement = _statement()

    assert create_body(statement) == {"statement": statement}


def test_create_body_wraps_statement_with_qualifiers_and_references():
    statement = _full_statement()

    assert create_body(statement) == {"statement": statement}


def test_refine_value_patch_tests_old_value_before_replacing():
    statement = _statement()
    new_value = {
        "type": "value",
        "content": dict(_TIME, time="+2020-01-01T00:00:00Z", precision=11),
    }

    assert refine_value_patch(statement, new_value) == {
        "patch": [
            {"op": "test", "path": "/value", "value": statement["value"]},
            {"op": "replace", "path": "/value", "value": new_value},
        ]
    }


def test_refine_qualifier_patch_tests_exact_element_before_replacing():
    statement = _full_statement()
    new_qualifier = {
        "property": {"id": "P580", "data_type": "time"},
        "value": {"type": "value", "content": dict(_TIME, precision=11)},
    }

    result = refine_qualifier_patch(statement, 0, new_qualifier)

    assert result == {
        "patch": [
            {
                "op": "test",
                "path": "/qualifiers/0",
                "value": _START_TIME_QUALIFIER,
            },
            {
                "op": "replace",
                "path": "/qualifiers/0",
                "value": new_qualifier,
            },
        ]
    }


def test_append_qualifier_patch_tests_existing_array_before_adding():
    statement = _full_statement()

    result = append_qualifier_patch(statement, _END_TIME_QUALIFIER)

    assert result == {
        "patch": [
            {
                "op": "test",
                "path": "/qualifiers",
                "value": [_START_TIME_QUALIFIER, _END_TIME_QUALIFIER],
            },
            {"op": "add", "path": "/qualifiers/-", "value": _END_TIME_QUALIFIER},
        ]
    }


def test_append_qualifier_patch_missing_key_tests_empty_array():
    """A missing qualifiers key is an empty array on Wikidata's document."""
    statement = _statement()

    result = append_qualifier_patch(statement, _START_TIME_QUALIFIER)

    assert result == {
        "patch": [
            {"op": "test", "path": "/qualifiers", "value": []},
            {"op": "add", "path": "/qualifiers/-", "value": _START_TIME_QUALIFIER},
        ]
    }


def test_append_reference_patch_tests_existing_array_before_adding():
    statement = _full_statement()

    result = append_reference_patch(statement, _URL_REFERENCE)

    assert result == {
        "patch": [
            {
                "op": "test",
                "path": "/references",
                "value": [_URL_REFERENCE],
            },
            {"op": "add", "path": "/references/-", "value": _URL_REFERENCE},
        ]
    }


def test_append_reference_patch_missing_key_tests_empty_array():
    """A missing references key is an empty array on Wikidata's document."""
    statement = _statement()

    result = append_reference_patch(statement, _URL_REFERENCE)

    assert result == {
        "patch": [
            {"op": "test", "path": "/references", "value": []},
            {"op": "add", "path": "/references/-", "value": _URL_REFERENCE},
        ]
    }


def test_builders_do_not_mutate_the_document():
    statement = _full_statement()
    snapshot = deepcopy(statement)
    new_value = {"type": "value", "content": dict(_TIME, precision=11)}

    create_body(statement)
    refine_value_patch(statement, new_value)
    refine_qualifier_patch(statement, 1, _START_TIME_QUALIFIER)
    append_qualifier_patch(statement, _START_TIME_QUALIFIER)
    append_reference_patch(statement, _URL_REFERENCE)

    assert statement == snapshot

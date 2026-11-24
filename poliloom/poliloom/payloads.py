"""Payload builders for persisted Actions.

Create Actions wrap a REST statement document as the body for
POST /v1/entities/items/{qid}/statements. Edit Actions carry an RFC 6902
JSON Patch whose ``test`` operations pin the patch to the document state it
was built against (no ETags): a failed test aborts the patch before any
mutation applies.

Statements always carry ``qualifiers`` and ``references`` arrays, matching the
Wikibase REST API response shape.
"""


def create_body(statement: dict) -> dict:
    """Wrap a REST statement body as ``{"statement": ...}`` for
    POST /v1/entities/items/{qid}/statements.
    """
    return {"statement": statement}


def statement_fact_guards(existing: dict) -> list[dict]:
    return [
        _test_value(existing),
        {"op": "test", "path": "/qualifiers", "value": existing["qualifiers"]},
    ]


def _test_value(existing: dict) -> dict:
    return {"op": "test", "path": "/value", "value": existing["value"]}


def refine_value_patch(existing: dict, new_value: dict) -> dict:
    """Precision refinement of the main value: test the current value, then
    replace it.
    """
    return {
        "patch": [
            _test_value(existing),
            {"op": "replace", "path": "/value", "value": new_value},
        ]
    }


def refine_qualifier_patch(
    existing: dict, qualifier_index: int, new_qualifier: dict
) -> dict:
    """Replace the qualifier only if the office and the target element still match."""
    return {
        "patch": [
            _test_value(existing),
            {
                "op": "test",
                "path": f"/qualifiers/{qualifier_index}",
                "value": existing["qualifiers"][qualifier_index],
            },
            {
                "op": "replace",
                "path": f"/qualifiers/{qualifier_index}",
                "value": new_qualifier,
            },
        ]
    }


def append_qualifier_patch(existing: dict, qualifier: dict) -> dict:
    """Append a qualifier only if the office and qualifiers still match."""
    return {
        "patch": [
            *statement_fact_guards(existing),
            {"op": "add", "path": "/qualifiers/-", "value": qualifier},
        ]
    }

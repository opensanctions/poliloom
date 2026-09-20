"""Payload builders for persisted Actions.

Create Actions wrap a REST statement document as the body for
POST /v1/entities/items/{qid}/statements. Edit Actions carry an RFC 6902
JSON Patch whose ``test`` operations pin the patch to the document state it
was built against (no ETags): a failed test aborts the patch before any
mutation applies.

Imported statements omit ``qualifiers``/``references`` when empty while the
Wikibase REST API always returns them as arrays; for tests, a missing key
means an empty array.
"""


def create_body(statement: dict) -> dict:
    """Wrap a REST statement body as ``{"statement": ...}`` for
    POST /v1/entities/items/{qid}/statements.
    """
    return {"statement": statement}


def refine_value_patch(existing: dict, new_value: dict) -> dict:
    """Precision refinement of the main value: test the current value, then
    replace it.
    """
    return {
        "patch": [
            {"op": "test", "path": "/value", "value": existing["value"]},
            {"op": "replace", "path": "/value", "value": new_value},
        ]
    }


def refine_qualifier_patch(
    existing: dict, qualifier_index: int, new_qualifier: dict
) -> dict:
    """Replace one qualifier: test the exact existing array element at
    ``qualifier_index``, then replace it.
    """
    return {
        "patch": [
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
    """Append a qualifier: test that ``/qualifiers`` still equals the current
    array, then add the qualifier at the end.
    """
    return {
        "patch": [
            {
                "op": "test",
                "path": "/qualifiers",
                "value": existing.get("qualifiers", []),
            },
            {"op": "add", "path": "/qualifiers/-", "value": qualifier},
        ]
    }


def append_reference_patch(existing: dict, reference: dict) -> dict:
    """Append a reference: test that ``/references`` still equals the current
    array, then add the reference at the end.
    """
    return {
        "patch": [
            {
                "op": "test",
                "path": "/references",
                "value": existing.get("references", []),
            },
            {"op": "add", "path": "/references/-", "value": reference},
        ]
    }

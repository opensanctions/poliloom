"""Reference comparison shared by proposal persistence and Wikidata writes."""

import json
from collections.abc import Iterable


def _reference_identity(reference: dict) -> str:
    """Prefer the source URL and ignore retrieval dates and server hashes."""
    parts = reference["parts"]
    for property_id in ("P854", "P4656"):
        for part in parts:
            if (
                part["property"]["id"] == property_id
                and part["value"]["type"] == "value"
            ):
                return part["value"]["content"]
    return json.dumps(
        sorted(
            json.dumps((part["property"]["id"], part["value"]), sort_keys=True)
            for part in parts
            if part["property"]["id"] != "P813"
        )
    )


def missing_references(proposed: Iterable[dict], existing: list[dict]) -> list[dict]:
    identities = {_reference_identity(reference) for reference in existing}
    missing = []
    for reference in proposed:
        identity = _reference_identity(reference)
        if identity not in identities:
            identities.add(identity)
            missing.append(reference)
    return missing


def is_wikimedia_import(reference: dict) -> bool:
    return any(
        part["property"]["id"] in {"P143", "P4656"} for part in reference["parts"]
    )

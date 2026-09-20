"""Read helpers for canonical Wikibase REST API statement documents.

Statements are stored as REST-shaped statement documents (one JSONB column
per statement) and read through these helpers instead of being decomposed.
Missing paths in a trusted document raise naturally; values of the wrong
type for a helper (e.g. a time content asked for as an entity ID) return
None.
"""

from .date import WikidataDate


def statement_property_id(document: dict) -> str:
    """Return the property ID (e.g. "P39") a statement belongs to."""
    return document["property"]["id"]


def statement_entity_id(document: dict) -> str | None:
    """Return the entity ID (e.g. "Q123") a statement points to.

    None when the main value is not a wikibase-item entity ID string
    (time values have dict content, somevalue/novalue have no content).
    """
    content = document["value"].get("content")
    if isinstance(content, str) and content.startswith("Q"):
        return content
    return None


def statement_time_value(document: dict) -> WikidataDate | None:
    """Return the main time value of a statement, or None if it is not a time value."""
    return _time_value(document["value"])


def find_qualifiers(document: dict, property_id: str) -> list[dict]:
    """Return the statement's qualifiers for a property, in document order."""
    return [
        qualifier
        for qualifier in document["qualifiers"]
        if qualifier["property"]["id"] == property_id
    ]


def qualifier_time_value(qualifier: dict) -> WikidataDate | None:
    """Return a qualifier's time value, or None if it is not a time value."""
    return _time_value(qualifier["value"])


def _time_value(value: dict) -> WikidataDate | None:
    """Parse a time value ({"type": "value", "content": {time, precision, ...}})."""
    content = value.get("content")
    if isinstance(content, dict) and "time" in content:
        return WikidataDate.from_wikidata_time(content["time"], content["precision"])
    return None

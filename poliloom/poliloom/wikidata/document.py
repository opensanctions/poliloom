"""Read helpers for canonical Wikibase REST API statement documents.

Statements are stored as REST-shaped statement documents (one JSONB column
per statement) and read through these helpers instead of being decomposed.
Missing paths in a trusted document raise naturally; values of the wrong
type for a helper (e.g. a time content asked for as an entity ID) return
None.
"""

from .date import WikidataDate

_START_QUALIFIER_ID = "P580"
_END_QUALIFIER_ID = "P582"


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


def format_timeframe(document: dict) -> str:
    """Human-readable P580/P582 timeframe of a statement for display.

    Returns " (1949 - 1953)", " (1949 - present)", " (until 1953)", or
    "" when the statement carries no timeframe qualifiers. Dates render
    at their stored precision.
    """
    start = _first_qualifier_time(document, _START_QUALIFIER_ID)
    end = _first_qualifier_time(document, _END_QUALIFIER_ID)

    if start is not None:
        timeframe = f" ({start.to_display_string()}"
        if end is not None:
            return f"{timeframe} - {end.to_display_string()})"
        return f"{timeframe} - present)"
    if end is not None:
        return f" (until {end.to_display_string()})"
    return ""


def _first_qualifier_time(document: dict, property_id: str) -> WikidataDate | None:
    """Time value of the first qualifier for a property, if any.

    Statements without qualifiers omit the key (import shape and create
    bodies do), so a missing key means no qualifiers.
    """
    if "qualifiers" not in document:
        return None
    qualifiers = find_qualifiers(document, property_id)
    if not qualifiers:
        return None
    return qualifier_time_value(qualifiers[0])


def _time_value(value: dict) -> WikidataDate | None:
    """Parse a time value ({"type": "value", "content": {time, precision, ...}})."""
    content = value.get("content")
    if isinstance(content, dict) and "time" in content:
        return WikidataDate.from_wikidata_time(content["time"], content["precision"])
    return None

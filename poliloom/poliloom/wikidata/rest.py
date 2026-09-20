"""Convert Action API claim JSON from Wikidata dumps to REST API statement documents.

Statements are stored canonically in their Wikibase REST API shape. The dump
produces Action API shaped claims; this module is the import boundary where
the shape is converted once.
"""

_TIME_KEYS = ("time", "precision", "calendarmodel")


def action_api_statement_to_rest(claim: dict) -> dict:
    """Convert an Action API claim to a REST API statement document.

    The dump is a trusted input: claims missing required fields fail with
    KeyError or TypeError rather than being validated up front.
    """
    mainsnak = claim["mainsnak"]
    statement = {
        "id": claim["id"],
        "rank": claim["rank"],
        "property": {
            "id": mainsnak["property"],
            "data_type": mainsnak["datatype"],
        },
        "value": _snak_value(mainsnak),
    }

    qualifiers = _snak_map_to_rest(
        claim.get("qualifiers", {}), claim.get("qualifiers-order")
    )
    if qualifiers:
        statement["qualifiers"] = qualifiers

    references = claim.get("references", [])
    if references:
        statement["references"] = [
            _reference_to_rest(reference) for reference in references
        ]

    return statement


def _snak_value(snak: dict) -> dict:
    """Build the REST value object for a snak; somevalue/novalue have no content."""
    value = {"type": snak["snaktype"]}
    if value["type"] == "value":
        value["content"] = _datavalue_content(snak["datavalue"])
    return value


def _datavalue_content(datavalue: dict) -> str | dict:
    """Convert an Action API datavalue to REST value content.

    wikibase-entityid collapses to the entity ID string, time drops
    before/after/timezone, and globecoordinate drops altitude. Other supported
    types (string, url, quantity, monolingualtext) pass through unchanged.
    """
    if datavalue["type"] == "wikibase-entityid":
        return datavalue["value"]["id"]
    if datavalue["type"] == "time":
        return {key: datavalue["value"][key] for key in _TIME_KEYS}
    if datavalue["type"] == "globecoordinate":
        return {
            key: value for key, value in datavalue["value"].items() if key != "altitude"
        }
    return datavalue["value"]


def _snak_map_to_rest(snak_map: dict, order: list[str] | None) -> list[dict]:
    """Flatten an Action API ``{property_id: [snaks]}`` map to ordered REST snaks.

    ``order`` (``qualifiers-order`` or a reference's ``snaks-order``) decides
    the property sequence when present, otherwise the map's insertion order.
    """
    property_ids = order if order is not None else snak_map
    return [_snak_to_rest(snak) for pid in property_ids for snak in snak_map[pid]]


def _snak_to_rest(snak: dict) -> dict:
    return {
        "property": {
            "id": snak["property"],
            "data_type": snak["datatype"],
        },
        "value": _snak_value(snak),
    }


def _reference_to_rest(reference: dict) -> dict:
    return {
        "hash": reference["hash"],
        "parts": _snak_map_to_rest(reference["snaks"], reference.get("snaks-order")),
    }

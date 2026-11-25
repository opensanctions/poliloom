"""Statement facts and the supported proposal transitions."""

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from .models import Action
from .wikidata.date import WikidataDate

_DATE_PROPERTIES = {"P569", "P570"}
_ENTITY_PROPERTIES = {"P19", "P27", "P39"}
_TERM_QUALIFIERS = {"P580", "P582"}


def _fact_snak(snak: dict) -> dict:
    prop = snak["property"]
    value = snak["value"]
    return {
        "property": {key: prop[key] for key in ("id", "data_type") if key in prop},
        "value": {
            "type": value["type"],
            **({"content": deepcopy(value["content"])} if "content" in value else {}),
        },
    }


def statement_fact(document: dict) -> dict:
    """Snapshot a REST statement's property, value and every qualifier value."""
    return {
        **_fact_snak(document),
        "qualifiers": [_fact_snak(snak) for snak in document["qualifiers"]],
    }


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def qualifier_key(snak: dict) -> str:
    fact = _fact_snak(snak)
    return _json((fact["property"]["id"], fact["value"]))


def fact_key(fact: dict) -> str:
    return _json((qualifier_key(fact), sorted(map(qualifier_key, fact["qualifiers"]))))


def action_group_key(action: Action) -> str:
    identity = _json(
        (
            str(action.politician_id),
            action.target_wikidata_statement_id,
            fact_key(action.before) if action.before is not None else None,
            fact_key(action.after),
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def _validate_snak(snak: dict) -> None:
    if not isinstance(snak, dict) or set(snak) != {"property", "value"}:
        raise ValueError("A snak must have a property and value")
    prop = snak["property"]
    if (
        not isinstance(prop, dict)
        or set(prop) - {"id", "data_type"}
        or not isinstance(prop.get("id"), str)
        or not re.fullmatch(r"P[1-9]\d*", prop["id"])
        or ("data_type" in prop and not isinstance(prop["data_type"], str))
    ):
        raise ValueError("A snak must have a valid property ID")
    value = snak["value"]
    if isinstance(value, dict):
        match value.get("type"):
            case "value" if set(value) == {"type", "content"} and isinstance(
                value["content"], (str, dict)
            ):
                return
            case "somevalue" | "novalue" if set(value) == {"type"}:
                return
    raise ValueError("Invalid Wikidata snak value")


def _date(value: dict) -> WikidataDate | None:
    if value["type"] != "value":
        return None
    content = value["content"]
    if (
        not isinstance(content, dict)
        or set(content) != {"time", "precision", "calendarmodel"}
        or not isinstance(content["time"], str)
        or not re.fullmatch(r"[+-]\d+-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content["time"])
        or type(content["precision"]) is not int
        or not 0 <= content["precision"] <= 14
        or not isinstance(content["calendarmodel"], str)
        or not content["calendarmodel"]
    ):
        raise ValueError("Invalid Wikidata time value")
    return WikidataDate.from_wikidata_time(content["time"], content["precision"])


def _validate_fact(fact: dict) -> None:
    if (
        not isinstance(fact, dict)
        or set(fact) != {"property", "value", "qualifiers"}
        or not isinstance(fact["qualifiers"], list)
    ):
        raise ValueError("A fact must have a property, value, and a list of qualifiers")
    _validate_snak({"property": fact["property"], "value": fact["value"]})
    property_id = fact["property"]["id"]
    value = fact["value"]
    if property_id in _DATE_PROPERTIES:
        _date(value)
    elif property_id in _ENTITY_PROPERTIES:
        if value["type"] == "value" and (
            not isinstance(value["content"], str)
            or not re.fullmatch(r"Q[1-9]\d*", value["content"])
        ):
            raise ValueError("Expected a Wikidata item ID")
    else:
        raise ValueError(f"Unsupported proposal property: {property_id}")
    for qualifier in fact["qualifiers"]:
        _validate_snak(qualifier)
        if qualifier["property"]["id"] in _TERM_QUALIFIERS:
            _date(qualifier["value"])


def _is_refined_date(old: dict, new: dict) -> bool:
    old_date, new_date = _date(old), _date(new)
    return new_date is not None and (
        old_date is None
        or (
            new_date.precision > old_date.precision
            and WikidataDate.dates_could_be_same(old_date, new_date)
        )
    )


@dataclass(frozen=True)
class Mutation:
    kind: Literal["value", "qualifier_replace", "qualifier_append"]
    old: dict | None
    new: dict


def proposal_mutation(before: dict, after: dict) -> Mutation | None:
    """Identify the sole supported change between two validated snapshots."""
    property_id = before["property"]["id"]
    if property_id != after["property"]["id"]:
        raise ValueError("A targeted proposal cannot change the statement property")

    old_qualifiers = {qualifier_key(q): q for q in before["qualifiers"]}
    new_qualifiers = {qualifier_key(q): q for q in after["qualifiers"]}
    before_counts = Counter(map(qualifier_key, before["qualifiers"]))
    after_counts = Counter(map(qualifier_key, after["qualifiers"]))
    removed = (before_counts - after_counts).total()
    added = (after_counts - before_counts).total()
    if _json(before["value"]) != _json(after["value"]):
        if (
            property_id in _DATE_PROPERTIES
            and not (removed or added)
            and _is_refined_date(before["value"], after["value"])
        ):
            return Mutation("value", before["value"], after["value"])
    elif not (removed or added):
        return None
    elif property_id == "P39" and added == 1 and removed <= 1:
        new = new_qualifiers[next(iter(after_counts - before_counts))]
        qualifier_id = new["property"]["id"]
        if qualifier_id in _TERM_QUALIFIERS:
            if removed:
                old = old_qualifiers[next(iter(before_counts - after_counts))]
                if old["property"]["id"] == qualifier_id and _is_refined_date(
                    old["value"], new["value"]
                ):
                    return Mutation("qualifier_replace", old, new)
            elif _date(new["value"]) is not None and not any(
                q["property"]["id"] == qualifier_id for q in before["qualifiers"]
            ):
                return Mutation("qualifier_append", None, new)
    raise ValueError("Only one supported value or timeframe refinement is allowed")


def validate_proposal(action: Action, politician_qid: str) -> None:
    """Validate at proposal persistence and before attempting a Wikidata write."""
    _validate_fact(action.after)
    target = action.target_wikidata_statement_id
    if (target is None) != (action.before is None):
        raise ValueError("A target and its before snapshot must be provided together")
    if target is not None:
        owner, separator, identifier = target.partition("$")
        if not separator or not identifier or owner.upper() != politician_qid:
            raise ValueError(
                f"Target statement {target} does not belong to {politician_qid}"
            )
        _validate_fact(action.before)
        proposal_mutation(action.before, action.after)

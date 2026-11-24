"""Decision core for enrichment: what Action (if any) a candidate warrants.

Enrichment extracts candidate statements (REST shape) from web sources.
This module compares one candidate against a politician's cached statement
documents and decides the single logical change to persist, if any:

- ``create``: a new statement (POST body via payloads.create_body)
- ``edit``: a guarded patch against one existing statement, with or without
  a change to its value or qualifiers

``persist_decision`` records the proposed write, including any source
reference, and links it to the supporting evidence.

Every rule below operates only on documents of the candidate's property.
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from .comparison import StatementComparison, compare_statement, is_timeframe_subsumed
from .models import Action, ActionEvidence, ActionKind, Politician, Source, Statement
from .payloads import (
    append_qualifier_patch,
    create_body,
    refine_qualifier_patch,
    refine_value_patch,
    statement_fact_guards,
)
from .wikidata.date import WikidataDate
from .wikidata.document import (
    find_qualifiers,
    qualifier_time_value,
    statement_property_id,
)
from .wikidata.references import missing_references

_DATE_PROPERTY_IDS = frozenset({"P569", "P570"})
_ENTITY_PROPERTY_IDS = frozenset({"P19", "P27"})
_POSITION_PROPERTY_ID = "P39"
_START_QUALIFIER_ID = "P580"
_END_QUALIFIER_ID = "P582"

_TIMEFRAME_QUALIFIER_IDS = (_START_QUALIFIER_ID, _END_QUALIFIER_ID)


@dataclass
class Decision:
    """One logical change to persist for a candidate statement.

    ``target_index`` is the index into the property-filtered existing
    documents (the subset of ``existing_documents`` sharing the candidate's
    property), not into the full list. It is None for creates.
    """

    kind: Literal["create", "edit"]
    payload: dict
    target_index: int | None = None


def plan(candidate: dict, existing_documents: list[dict]) -> Decision | None:
    """Plan how a candidate creates, changes, or supports a statement."""
    property_id = statement_property_id(candidate)
    same_property_documents = [
        document
        for document in existing_documents
        if statement_property_id(document) == property_id
    ]

    if property_id in _DATE_PROPERTY_IDS:
        return _plan_date(candidate, same_property_documents)
    if property_id == _POSITION_PROPERTY_ID:
        return _plan_position(candidate, same_property_documents)
    if property_id in _ENTITY_PROPERTY_IDS:
        return _plan_entity(candidate, same_property_documents)
    raise ValueError(f"Unsupported property in planning: {property_id}")


def persist_decision(
    db: Session,
    politician: Politician,
    decision: Decision | None,
    existing_statements: list[Statement],
    source: Source,
    supporting_quotes: list[str],
) -> Action | None:
    """Persist a planned Decision as a pending Action with evidence.

    ``existing_statements`` must be the same property-filtered,
    order-preserved list of Statement objects whose documents were passed
    to ``plan()``; a decision's ``target_index`` indexes into it.

    Each proposal has its own Action and evidence. A Wikimedia import marker
    by itself does not warrant editing an existing statement.
    """
    if decision is None:
        return None

    if decision.kind == "create":
        kind = ActionKind.CREATE_STATEMENT
        statement_id = None
        payload = create_body(
            {
                **decision.payload["statement"],
                "references": [{"parts": source.create_references_json()}],
            }
        )
    else:
        kind = ActionKind.EDIT_STATEMENT
        target = existing_statements[decision.target_index]
        statement_id = target.id
        patch = decision.payload["patch"]
        reference_only = all(operation["op"] == "test" for operation in patch)
        if source.wikipedia_project_id:
            if reference_only:
                return None
        else:
            reference = {"parts": source.create_references_json()}
            if reference_only and not missing_references(
                [reference], target.document["references"]
            ):
                return None
            patch = [*patch, {"op": "add", "path": "/references/-", "value": reference}]
        payload = {"patch": patch}

    action = Action(
        politician_id=politician.id,
        kind=kind,
        payload=payload,
        statement_id=statement_id,
    )
    db.add(action)
    db.add(
        ActionEvidence(
            action=action, source=source, supporting_quotes=supporting_quotes
        )
    )
    db.flush()
    return action


def _plan_date(candidate: dict, same_property_documents: list[dict]) -> Decision:
    """P569/P570: refine the sole compatible statement, else create."""
    compatible = _compatible_targets(candidate, same_property_documents)

    if len(compatible) != 1:
        # Zero compatible targets: no statement states this date. More than
        # one: ambiguous, never guess which statement to act on.
        return _create_decision(candidate)

    index, document, comparison = compatible[0]
    if comparison is StatementComparison.CANDIDATE_REFINES_EXISTING:
        return Decision("edit", refine_value_patch(document, candidate["value"]), index)

    return _support_decision(document, index)


def _plan_position(
    candidate: dict, same_property_documents: list[dict]
) -> Decision | None:
    """P39: qualifier refinement on the sole compatible statement, else create."""
    same_position = [
        (index, document, comparison)
        for index, document, comparison in _comparisons(
            candidate, same_property_documents
        )
        if comparison is not StatementComparison.NO_MATCH
    ]

    if is_timeframe_subsumed([document for _, document, _ in same_position], candidate):
        # Existing consecutive terms already cover the candidate span: no
        # refinement or creation, only a reference on a single equivalent
        # target.
        equivalent = [
            (index, document)
            for index, document, comparison in same_position
            if comparison is StatementComparison.EQUIVALENT
        ]
        if len(equivalent) == 1:
            index, document = equivalent[0]
            return _support_decision(document, index)
        return None

    compatible = [
        (index, document, comparison)
        for index, document, comparison in same_position
        if comparison
        not in (StatementComparison.NO_MATCH, StatementComparison.INCOMPARABLE)
    ]

    if len(compatible) != 1:
        return _create_decision(candidate)

    index, document, comparison = compatible[0]
    if comparison is not StatementComparison.CANDIDATE_REFINES_EXISTING:
        return _support_decision(document, index)
    return _position_refinement_decision(candidate, document, index)


def _position_refinement_decision(
    candidate: dict, document: dict, index: int
) -> Decision:
    """Pick the one qualifier change for a refining position candidate.

    When several timeframe qualifiers need changes, appends win over
    replacements (a missing qualifier is worth more than a narrower one),
    and P580 is handled before P582.
    """
    appends: list[dict] = []
    refinements: list[tuple[str, dict]] = []
    for qualifier_id in _TIMEFRAME_QUALIFIER_IDS:
        candidate_qualifier = _first_qualifier(candidate, qualifier_id)
        if candidate_qualifier is None:
            continue
        target_qualifier = _first_qualifier(document, qualifier_id)
        if target_qualifier is None:
            appends.append(candidate_qualifier)
            continue
        candidate_date = qualifier_time_value(candidate_qualifier)
        target_date = qualifier_time_value(target_qualifier)
        more_precise = WikidataDate.more_precise_date(candidate_date, target_date)
        if more_precise is candidate_date:
            refinements.append((qualifier_id, candidate_qualifier))

    if appends:
        return Decision("edit", append_qualifier_patch(document, appends[0]), index)
    if refinements:
        qualifier_id, qualifier = refinements[0]
        for index_in_document, existing in enumerate(document["qualifiers"]):
            if existing["property"]["id"] == qualifier_id:
                break
        else:
            raise ValueError(f"Statement has no {qualifier_id} qualifier")
        return Decision(
            "edit",
            refine_qualifier_patch(document, index_in_document, qualifier),
            index,
        )

    return _support_decision(document, index)


def _plan_entity(candidate: dict, same_property_documents: list[dict]) -> Decision:
    """P19/P27: support the sole equivalent statement, else create.

    An entity value is never replaced: a differing candidate is a new fact.
    """
    equivalent = [
        (index, document)
        for index, document, comparison in _comparisons(
            candidate, same_property_documents
        )
        if comparison is StatementComparison.EQUIVALENT
    ]

    if len(equivalent) != 1:
        return _create_decision(candidate)

    index, document = equivalent[0]
    return _support_decision(document, index)


def _support_decision(document: dict, index: int) -> Decision:
    # The source supports this value and qualifiers, not whatever may replace them.
    return Decision("edit", {"patch": statement_fact_guards(document)}, index)


def _create_decision(candidate: dict) -> Decision:
    """Build a create Action for the candidate."""
    statement = dict(candidate)
    statement["references"] = []
    statement.setdefault("rank", "normal")
    return Decision("create", create_body(statement))


def _comparisons(
    candidate: dict, same_property_documents: list[dict]
) -> list[tuple[int, dict, StatementComparison]]:
    """Compare the candidate against each same-property document, in order."""
    return [
        (index, document, compare_statement(candidate, document))
        for index, document in enumerate(same_property_documents)
    ]


def _compatible_targets(
    candidate: dict, same_property_documents: list[dict]
) -> list[tuple[int, dict, StatementComparison]]:
    """Documents whose comparison leaves room for exactly one shared fact."""
    return [
        (index, document, comparison)
        for index, document, comparison in _comparisons(
            candidate, same_property_documents
        )
        if comparison
        in (
            StatementComparison.EQUIVALENT,
            StatementComparison.EXISTING_SUBSUMES_CANDIDATE,
            StatementComparison.CANDIDATE_REFINES_EXISTING,
        )
    ]


def _first_qualifier(document: dict, property_id: str) -> dict | None:
    """First qualifier for a property, or None when absent."""
    qualifiers = find_qualifiers(document, property_id)
    return qualifiers[0] if qualifiers else None

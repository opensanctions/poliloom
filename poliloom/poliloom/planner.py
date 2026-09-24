"""Decision core for enrichment: what Action (if any) a candidate warrants.

Enrichment extracts candidate statements (REST shape) from web sources.
This module compares one candidate against a politician's cached statement
documents and decides the single logical change to persist, if any:

- ``create``: a new statement (POST body via payloads.create_body)
- ``edit``: an RFC 6902 patch against one existing statement
  (payloads.append_qualifier_patch / refine_qualifier_patch /
  refine_value_patch / append_reference_patch)

``persist_decision`` turns a planned Decision into a persisted Action with
source evidence, deduplicating against pending Actions.

Every rule below operates only on documents of the candidate's property.
"""

import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from .comparison import StatementComparison, compare_statement, is_timeframe_subsumed
from .models import Action, ActionEvidence, ActionKind, Politician, Source, Statement
from .payloads import (
    append_qualifier_patch,
    append_reference_patch,
    create_body,
    refine_qualifier_patch,
    refine_value_patch,
)
from .wikidata.date import WikidataDate
from .wikidata.document import (
    find_qualifiers,
    qualifier_time_value,
    statement_property_id,
)

_REFERENCE_URL_ID = "P854"
_WIKIMEDIA_IMPORT_URL_ID = "P4656"
_RETRIEVED_AT_ID = "P813"

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


def reference_identity(reference: dict) -> str:
    """Canonical identity string for a reference.

    The reference URL part (P854) identifies the reference when present,
    else the Wikimedia import URL part (P4656), else the canonical JSON of
    the remaining parts. Retrieval dates (P813) and the read-only ``hash``
    never affect identity.
    """
    parts = reference.get("parts", [])
    for property_id in (_REFERENCE_URL_ID, _WIKIMEDIA_IMPORT_URL_ID):
        for part in parts:
            if part["property"]["id"] == property_id:
                return part["value"]["content"]

    identifying_parts = [
        part for part in parts if part["property"]["id"] != _RETRIEVED_AT_ID
    ]
    return json.dumps(identifying_parts, sort_keys=True, separators=(",", ":"))


def reference_present(document: dict, reference: dict) -> bool:
    """Check whether a statement document already carries a reference.

    A missing ``references`` key means the document has none (import shape).
    """
    identity = reference_identity(reference)
    return any(
        reference_identity(existing) == identity
        for existing in document.get("references", [])
    )


def plan(
    candidate: dict, existing_documents: list[dict], reference: dict
) -> Decision | None:
    """Decide what change (if any) to persist for a candidate statement.

    Args:
        candidate: REST statement body (``property``/``value``, optional
            ``qualifiers``) extracted from a source.
        existing_documents: the politician's cached statement documents, all
            properties; filtered to the candidate's property internally.
        reference: proposed REST reference object (``{"parts": [...]}``)
            from the evidence source.

    Returns None when the existing data already covers the candidate.
    """
    property_id = statement_property_id(candidate)
    same_property_documents = [
        document
        for document in existing_documents
        if statement_property_id(document) == property_id
    ]

    if property_id in _DATE_PROPERTY_IDS:
        return _plan_date(candidate, same_property_documents, reference)
    if property_id == _POSITION_PROPERTY_ID:
        return _plan_position(candidate, same_property_documents, reference)
    if property_id in _ENTITY_PROPERTY_IDS:
        return _plan_entity(candidate, same_property_documents, reference)

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

    A pending Action (``is_accepted IS NULL``) on the same politician with
    the same kind, statement_id, and equal canonicalized payload is not
    duplicated: the source is attached as further evidence on it instead
    (quotes merged by union when the source is already attached). Decided
    actions are immutable and never deduplication targets.

    Returns the Action the evidence was attached to, or None when the
    decision is None (nothing to persist).
    """
    if decision is None:
        return None

    kind = (
        ActionKind.CREATE_STATEMENT
        if decision.kind == "create"
        else ActionKind.EDIT_STATEMENT
    )
    statement_id = None
    if decision.kind == "edit":
        statement_id = existing_statements[decision.target_index].id

    payload_json = json.dumps(decision.payload, sort_keys=True)
    statement_filter = (
        Action.statement_id.is_(None)
        if statement_id is None
        else Action.statement_id == statement_id
    )
    pending_actions = (
        db.query(Action)
        .filter(
            Action.politician_id == politician.id,
            Action.kind == kind,
            Action.is_accepted.is_(None),
            statement_filter,
        )
        .all()
    )
    for action in pending_actions:
        if json.dumps(action.payload, sort_keys=True) != payload_json:
            continue
        _attach_evidence(db, action, source, supporting_quotes)
        return action

    action = Action(
        politician_id=politician.id,
        kind=kind,
        payload=decision.payload,
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


def _attach_evidence(
    db: Session, action: Action, source: Source, supporting_quotes: list[str]
) -> None:
    """Attach the source as evidence, merging quotes when already attached."""
    evidence = (
        db.query(ActionEvidence)
        .filter_by(action_id=action.id, source_id=source.id)
        .first()
    )
    if evidence:
        evidence.supporting_quotes = list(
            set((evidence.supporting_quotes or []) + supporting_quotes)
        )
    else:
        db.add(
            ActionEvidence(
                action=action, source=source, supporting_quotes=supporting_quotes
            )
        )


def _plan_date(
    candidate: dict, same_property_documents: list[dict], reference: dict
) -> Decision | None:
    """P569/P570: refine the sole compatible statement, else create."""
    compatible = _compatible_targets(candidate, same_property_documents)

    if len(compatible) != 1:
        # Zero compatible targets: no statement states this date. More than
        # one: ambiguous, never guess which statement to act on.
        return _create_decision(candidate, reference)

    index, document, comparison = compatible[0]
    if comparison is StatementComparison.CANDIDATE_REFINES_EXISTING:
        return Decision("edit", refine_value_patch(document, candidate["value"]), index)

    # EQUIVALENT or EXISTING_SUBSUMES_CANDIDATE: the fact is known; only a
    # missing reference can change anything.
    return _reference_append_decision(document, index, reference)


def _plan_position(
    candidate: dict, same_property_documents: list[dict], reference: dict
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
            return _reference_append_decision(document, index, reference)
        return None

    compatible = [
        (index, document, comparison)
        for index, document, comparison in same_position
        if comparison
        not in (StatementComparison.NO_MATCH, StatementComparison.INCOMPARABLE)
    ]

    if len(compatible) != 1:
        return _create_decision(candidate, reference)

    index, document, comparison = compatible[0]
    if comparison is not StatementComparison.CANDIDATE_REFINES_EXISTING:
        # EQUIVALENT or EXISTING_SUBSUMES_CANDIDATE: only a missing
        # reference can change anything.
        return _reference_append_decision(document, index, reference)
    return _position_refinement_decision(candidate, document, index, reference)


def _position_refinement_decision(
    candidate: dict, document: dict, index: int, reference: dict
) -> Decision | None:
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

    # The candidate carries no timeframe qualifiers here (the comparison's
    # has-dates special case cannot produce CANDIDATE_REFINES_EXISTING for
    # it), so only a missing reference can change anything.
    return _reference_append_decision(document, index, reference)


def _plan_entity(
    candidate: dict, same_property_documents: list[dict], reference: dict
) -> Decision | None:
    """P19/P27: reference the sole equivalent statement, else create.

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
        return _create_decision(candidate, reference)

    index, document = equivalent[0]
    return _reference_append_decision(document, index, reference)


def _reference_append_decision(
    document: dict, index: int, reference: dict
) -> Decision | None:
    """Append the reference to a statement, or None when already present."""
    if reference_present(document, reference):
        return None
    return Decision("edit", append_reference_patch(document, reference), index)


def _create_decision(candidate: dict, reference: dict) -> Decision:
    """Build a create Action for the candidate, referenced by the source."""
    statement = dict(candidate)
    statement["references"] = [reference]
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
    """First qualifier for a property, or None when absent.

    Statements without qualifiers omit the key (import shape and create
    bodies do), so a missing key means no qualifiers.
    """
    if "qualifiers" not in document:
        return None
    qualifiers = find_qualifiers(document, property_id)
    if not qualifiers:
        return None
    return qualifiers[0]

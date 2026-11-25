"""Plan statement proposals from extractions and cached Wikidata facts."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .comparison import StatementComparison, compare_statement, is_timeframe_subsumed
from .models import Action, ActionEvidence, Politician, Source, Statement
from .proposals import fact_key, statement_fact, validate_proposal
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
    property), not into the full list. New statements have no target or before fact.
    """

    after: dict
    before: dict | None = None
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

    target_id = None
    if decision.target_index is None:
        references = [{"parts": source.create_references_json()}]
    else:
        target = existing_statements[decision.target_index]
        if target.politician_id != politician.id:
            raise ValueError("Target statement belongs to another politician")
        target_id = target.wikidata_statement_id
        reference_only = fact_key(decision.before) == fact_key(decision.after)
        references = (
            []
            if source.wikipedia_project_id
            else [{"parts": source.create_references_json()}]
        )
        if reference_only and not missing_references(
            references, target.document["references"]
        ):
            return None

    action = Action(
        politician_id=politician.id,
        target_wikidata_statement_id=target_id,
        before=decision.before,
        after=decision.after,
        references_to_add=references,
    )
    validate_proposal(action, politician.wikidata_id)
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
        before = statement_fact(document)
        after = {**before, "value": statement_fact(candidate)["value"]}
        return Decision(after=after, before=before, target_index=index)

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

    if not (appends or refinements):
        return _support_decision(document, index)

    before = statement_fact(document)
    after = statement_fact(document)
    if appends:
        after["qualifiers"].append(appends[0])
    else:
        qualifier_id, qualifier = refinements[0]
        slot = next(
            i
            for i, existing in enumerate(after["qualifiers"])
            if existing["property"]["id"] == qualifier_id
        )
        after["qualifiers"][slot] = qualifier
    return Decision(after=statement_fact(after), before=before, target_index=index)


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
    fact = statement_fact(document)
    return Decision(after=fact, before=fact, target_index=index)


def _create_decision(candidate: dict) -> Decision:
    return Decision(after=statement_fact(candidate))


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

"""Create review actions from extracted and cached Wikidata statements."""

from dataclasses import dataclass

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
class _StatementChange:
    after: dict
    before: dict | None = None
    target: Statement | None = None


def create_action(
    politician: Politician,
    candidate: dict,
    existing_statements: list[Statement],
    source: Source,
    supporting_quotes: list[str],
) -> Action | None:
    """Create a pending Action with evidence, or None when no action is useful."""
    property_id = statement_property_id(candidate)
    same_property_statements = [
        statement
        for statement in existing_statements
        if statement_property_id(statement.document) == property_id
    ]
    change = _statement_change(candidate, same_property_statements)
    if change is None:
        return None

    if change.target is None:
        target_id = None
        references = [{"parts": source.create_references_json()}]
    else:
        target = change.target
        if target.politician_id != politician.id:
            raise ValueError("Target statement belongs to another politician")
        target_id = target.wikidata_statement_id
        reference_only = fact_key(change.before) == fact_key(change.after)
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
        before=change.before,
        after=change.after,
        references_to_add=references,
    )
    ActionEvidence(action=action, source=source, supporting_quotes=supporting_quotes)
    validate_proposal(action, politician.wikidata_id)
    return action


def _statement_change(
    candidate: dict, same_property_statements: list[Statement]
) -> _StatementChange | None:
    property_id = statement_property_id(candidate)
    if property_id in _DATE_PROPERTY_IDS:
        return _date_change(candidate, same_property_statements)
    if property_id == _POSITION_PROPERTY_ID:
        return _position_change(candidate, same_property_statements)
    if property_id in _ENTITY_PROPERTY_IDS:
        return _entity_change(candidate, same_property_statements)
    raise ValueError(f"Unsupported property in action creation: {property_id}")


def _date_change(
    candidate: dict, same_property_statements: list[Statement]
) -> _StatementChange:
    """P569/P570: refine the sole compatible statement, else create."""
    compatible = _compatible_targets(candidate, same_property_statements)

    if len(compatible) != 1:
        # Zero compatible targets: no statement states this date. More than
        # one: ambiguous, never guess which statement to act on.
        return _create(candidate)

    target, comparison = compatible[0]
    document = target.document
    if comparison is StatementComparison.CANDIDATE_REFINES_EXISTING:
        before = statement_fact(document)
        after = {**before, "value": statement_fact(candidate)["value"]}
        return _StatementChange(after=after, before=before, target=target)

    return _support(target)


def _position_change(
    candidate: dict, same_property_statements: list[Statement]
) -> _StatementChange | None:
    """P39: qualifier refinement on the sole compatible statement, else create."""
    same_position = [
        (statement, comparison)
        for statement, comparison in _comparisons(candidate, same_property_statements)
        if comparison is not StatementComparison.NO_MATCH
    ]

    if is_timeframe_subsumed(
        [statement.document for statement, _ in same_position], candidate
    ):
        # Existing consecutive terms already cover the candidate span: no
        # refinement or creation, only a reference on a single equivalent
        # target.
        equivalent = [
            statement
            for statement, comparison in same_position
            if comparison is StatementComparison.EQUIVALENT
        ]
        if len(equivalent) == 1:
            return _support(equivalent[0])
        return None

    compatible = [
        (statement, comparison)
        for statement, comparison in same_position
        if comparison
        not in (StatementComparison.NO_MATCH, StatementComparison.INCOMPARABLE)
    ]

    if len(compatible) != 1:
        return _create(candidate)

    target, comparison = compatible[0]
    if comparison is not StatementComparison.CANDIDATE_REFINES_EXISTING:
        return _support(target)
    return _position_refinement(candidate, target)


def _position_refinement(candidate: dict, target: Statement) -> _StatementChange:
    """Pick the one qualifier change for a refining position candidate.

    When several timeframe qualifiers need changes, appends win over
    replacements (a missing qualifier is worth more than a narrower one),
    and P580 is handled before P582.
    """
    document = target.document
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
        return _support(target)

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
    return _StatementChange(after=after, before=before, target=target)


def _entity_change(
    candidate: dict, same_property_statements: list[Statement]
) -> _StatementChange:
    """P19/P27: support the sole equivalent statement, else create.

    An entity value is never replaced: a differing candidate is a new fact.
    """
    equivalent = [
        statement
        for statement, comparison in _comparisons(candidate, same_property_statements)
        if comparison is StatementComparison.EQUIVALENT
    ]

    if len(equivalent) != 1:
        return _create(candidate)

    return _support(equivalent[0])


def _support(target: Statement) -> _StatementChange:
    fact = statement_fact(target.document)
    return _StatementChange(after=fact, before=fact, target=target)


def _create(candidate: dict) -> _StatementChange:
    return _StatementChange(after=statement_fact(candidate))


def _comparisons(
    candidate: dict, same_property_statements: list[Statement]
) -> list[tuple[Statement, StatementComparison]]:
    """Compare the candidate against each same-property statement, in order."""
    return [
        (statement, compare_statement(candidate, statement.document))
        for statement in same_property_statements
    ]


def _compatible_targets(
    candidate: dict, same_property_statements: list[Statement]
) -> list[tuple[Statement, StatementComparison]]:
    """Statements whose comparison leaves room for exactly one shared fact."""
    return [
        (statement, comparison)
        for statement, comparison in _comparisons(candidate, same_property_statements)
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

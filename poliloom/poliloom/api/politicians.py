"""Politicians API endpoints."""

import asyncio
from datetime import UTC, datetime

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db_session
from ..enrichment_queue import create_enrichment_sources
from ..models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionKind,
    ActionSkip,
    Politician,
    Source,
    SourceLanguage,
    WikidataEntity,
)
from ..review_queue import (
    available_to_user,
    claim_next,
    claim_visible_actions,
    count_serveable,
    get_claim_ttl,
    language_visible,
    not_skipped,
    pending,
    refresh_claims,
)
from ..scheduling import (
    enrich_until_serveable,
    has_enrichment_candidate,
    process_source_task,
)
from ..sse import DecisionCountEvent, event_bus
from ..wikidata.execution import apply_action
from .auth import User, get_current_user
from .schemas import (
    ActionEvidenceResponse,
    ActionResponse,
    CreateSourceRequest,
    EnrichmentMetadata,
    NextPoliticianResponse,
    PatchActionsRequest,
    PatchActionsResponse,
    PoliticianResponse,
    SourceResponse,
    StatementResponse,
    SubmittedAction,
    TermMaps,
)

router = APIRouter()

# =============================================================================
# Helper function to build politician responses
# =============================================================================


def _term_maps(entity: WikidataEntity) -> TermMaps:
    """Build TermMaps from a WikidataEntity's language-keyed term columns."""
    return TermMaps(
        labels=entity.labels,
        descriptions=entity.descriptions,
        aliases=entity.aliases,
    )


def build_politician_response(
    politician: Politician, db: Session
) -> PoliticianResponse:
    """Build PoliticianResponse with context statements and reviewable actions."""

    entity_ids = {
        entity_id
        for entity_id in (
            *(statement.entity_id for statement in politician.statements),
            *(action.entity_id for action in politician.actions),
        )
        if entity_id is not None
    }
    entities_by_id = (
        {
            entity.wikidata_id: entity
            for entity in db.execute(
                select(WikidataEntity).where(WikidataEntity.wikidata_id.in_(entity_ids))
            ).scalars()
        }
        if entity_ids
        else {}
    )

    def entity_terms(entity_id: str | None) -> TermMaps | None:
        if entity_id is None:
            return None
        return _term_maps(entities_by_id[entity_id])

    statements = [
        StatementResponse(
            id=statement.id,
            document=statement.document,
            entity_terms=entity_terms(statement.entity_id),
        )
        for statement in politician.statements
    ]

    actions = [
        ActionResponse(
            id=action.id,
            kind=action.kind,
            statement_id=action.statement_id,
            payload=action.payload,
            entity_terms=entity_terms(action.entity_id),
            evidence=[
                ActionEvidenceResponse(
                    id=evidence.id,
                    source=SourceResponse.model_validate(evidence.source),
                    supporting_quotes=evidence.supporting_quotes,
                )
                for evidence in action.evidence
            ],
            is_accepted=action.is_accepted,
            applied_at=action.applied_at,
            error=action.error,
        )
        for action in politician.actions
    ]

    return PoliticianResponse(
        id=politician.id,
        wikidata_id=politician.wikidata_id,
        terms=_term_maps(politician.wikidata_entity),
        sources=[SourceResponse.model_validate(s) for s in politician.sources],
        statements=statements,
        actions=actions,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/next", response_model=NextPoliticianResponse)
async def get_next_politician(
    languages: list[str] = Query(...),
    countries: list[str] = Query(default=[]),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Claim and return the next deterministic review candidate.

    Serving creates per-action claims immediately. Background enrichment only
    maintains a floor of one additional serveable politician for these filters.
    """
    country_filter = countries or None
    qid = claim_next(db, str(current_user.user_id), languages, country_filter)
    if qid:
        if count_serveable(db, languages, country_filter) == 0:
            asyncio.create_task(enrich_until_serveable(languages, country_filter))
        return NextPoliticianResponse(
            wikidata_id=qid,
            meta=EnrichmentMetadata(has_enrichable_politicians=False),
        )

    has_candidates = has_enrichment_candidate(db, languages, countries)
    if has_candidates:
        asyncio.create_task(enrich_until_serveable(languages, country_filter))

    return NextPoliticianResponse(
        meta=EnrichmentMetadata(has_enrichable_politicians=has_candidates)
    )


@router.get("/search", response_model=list[PoliticianResponse])
async def search_politicians(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query for politicians",
    ),
    limit: int = Query(
        default=50, le=100, description="Maximum number of politicians to return"
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Search politicians by label.

    Returns matching politicians ranked by relevance with their context
    statements and pending reviewable actions.
    """
    entity_ids = Politician.find_similar(q, limit=limit)
    if not entity_ids:
        return []

    # Preserve search ranking order
    ordering = case(
        {eid: idx for idx, eid in enumerate(entity_ids)},
        value=Politician.wikidata_id,
    )

    user_id = str(current_user.user_id)
    action_filter = and_(
        pending(Action),
        not_skipped(Action, user_id),
        available_to_user(Action, user_id),
    )

    query = (
        Politician.query_base()
        .where(Politician.wikidata_id.in_(entity_ids))
        .order_by(ordering)
        .options(
            selectinload(Politician.statements),
            selectinload(Politician.actions.and_(action_filter)).options(
                selectinload(Action.evidence).selectinload(ActionEvidence.source),
            ),
        )
    )

    politicians = db.execute(query).scalars().all()

    return [build_politician_response(politician, db) for politician in politicians]


@router.get("/{qid}", response_model=PoliticianResponse)
async def get_politician(
    qid: str,
    languages: list[str] = Query(
        ...,
        description="Filter actions by language QIDs",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a single politician by Wikidata QID.

    All statements are returned as review context; actions are the
    pending ones visible to this user (language-visible, not skipped, and
    unclaimed or claimed by them). Creates sources for unclaimed Wikipedia
    projects matching the requested languages, scheduling their background
    processing.
    """
    user_id = str(current_user.user_id)
    action_filter = and_(
        pending(Action),
        language_visible(Action, languages),
        not_skipped(Action, user_id),
        available_to_user(Action, user_id),
    )
    source_filter = or_(
        exists(
            select(1).where(
                SourceLanguage.source_id == Source.id,
                SourceLanguage.language_id.in_(languages),
            )
        ),
        ~exists(select(1).where(SourceLanguage.source_id == Source.id)),
    )
    query = (
        Politician.query_base()
        .where(Politician.wikidata_id == qid)
        .options(
            selectinload(Politician.statements),
            selectinload(Politician.actions.and_(action_filter)).options(
                selectinload(Action.evidence)
                .selectinload(ActionEvidence.source)
                .selectinload(Source.source_languages),
            ),
            selectinload(Politician.sources.and_(source_filter)).selectinload(
                Source.source_languages
            ),
        )
        .execution_options(populate_existing=True)
        .with_for_update(of=Politician)
    )

    politician = db.execute(query).scalars().first()

    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    claim_visible_actions(db, user_id, politician, languages)
    new_sources = create_enrichment_sources(politician, db, languages=languages)

    response = build_politician_response(politician, db)

    db.commit()
    for source in new_sources:
        asyncio.create_task(process_source_task(source.id, politician.id))

    return response


def _action_envelope_error(submitted: SubmittedAction) -> str | None:
    """Validate the action envelope for its kind; return an error message or None."""
    if submitted.kind is ActionKind.CREATE_STATEMENT:
        statement = submitted.payload.get("statement")
        if not isinstance(statement, dict):
            return 'CREATE_STATEMENT payload must be {"statement": {...}}'
        prop = statement.get("property")
        if not isinstance(prop, dict) or not prop.get("id"):
            return "CREATE_STATEMENT statement.property.id is required"
        if "value" not in statement:
            return "CREATE_STATEMENT statement.value is required"
        return None
    if submitted.statement_id is None:
        return "EDIT_STATEMENT statement_id is required"
    if not isinstance(submitted.payload.get("patch"), list):
        return 'EDIT_STATEMENT payload must be {"patch": [...]}'
    return None


@router.patch("/{qid}/actions", response_model=PatchActionsResponse)
async def patch_actions(
    qid: str,
    request: PatchActionsRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Record submitted actions and skips for a politician.

    Each submission either updates an existing pending action (requires a
    live claim by the current user; the submitted object is truth, so kind,
    statement_id and payload are overwritten) or inserts a user-authored new
    action. Accepted actions are applied to Wikidata synchronously once the
    submissions are committed. Skips hide a pending action for the current
    user without deciding it.
    """
    errors = []

    politician = (
        db.execute(select(Politician).where(Politician.wikidata_id == qid))
        .scalars()
        .first()
    )
    if not politician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Politician with QID {qid} not found",
        )

    user_id = str(current_user.user_id)
    refresh_claims(db, user_id, politician.id)
    cutoff = datetime.now(UTC) - get_claim_ttl()

    decided_actions = []
    accepted_actions = []
    processed_count = 0

    for index, submitted in enumerate(request.actions):
        label = f"Action {submitted.id}" if submitted.id else f"actions[{index}]"
        try:
            envelope_error = _action_envelope_error(submitted)
            if envelope_error:
                errors.append(f"{label}: {envelope_error}")
                continue

            if submitted.id is not None:
                action = db.execute(
                    select(Action).where(Action.id == submitted.id).with_for_update()
                ).scalar_one_or_none()
                if action is None:
                    errors.append(f"Action {submitted.id} not found")
                    continue
                if action.politician_id != politician.id:
                    errors.append(
                        f"Action {submitted.id} does not belong to politician {qid}"
                    )
                    continue
                if action.is_accepted is not None:
                    errors.append(f"Action {submitted.id} is not pending")
                    continue
                live_claim = db.scalar(
                    select(ActionClaim.id).where(
                        ActionClaim.action_id == action.id,
                        ActionClaim.user_id == user_id,
                        ActionClaim.claimed_at > cutoff,
                    )
                )
                if live_claim is None:
                    errors.append(
                        f"Action {submitted.id} is not claimed by user {user_id}"
                    )
                    continue

                action.kind = submitted.kind
                action.statement_id = submitted.statement_id
                action.payload = submitted.payload
            else:
                action = Action(
                    politician_id=politician.id,
                    kind=submitted.kind,
                    statement_id=submitted.statement_id,
                    payload=submitted.payload,
                )
                db.add(action)
                db.flush()

            action.is_accepted = submitted.is_accepted
            action.decided_by_user_id = user_id
            action.decided_at = datetime.now(UTC)
            decided_actions.append(action)
            processed_count += 1
            if submitted.is_accepted:
                accepted_actions.append(action)

        except SQLAlchemyError as e:
            errors.append(f"Error processing action {label}: {e!s}")
            continue

    for skip_id in request.skips:
        try:
            action = db.execute(
                select(Action).where(Action.id == skip_id).with_for_update()
            ).scalar_one_or_none()
            if action is None:
                errors.append(f"Action {skip_id} not found")
                continue
            if action.politician_id != politician.id:
                errors.append(f"Action {skip_id} does not belong to politician {qid}")
                continue
            if action.is_accepted is not None:
                errors.append(f"Action {skip_id} is not pending")
                continue

            db.execute(
                pg_insert(ActionSkip)
                .values(user_id=user_id, action_id=skip_id)
                .on_conflict_do_nothing(index_elements=["user_id", "action_id"])
            )
            processed_count += 1

        except SQLAlchemyError as e:
            errors.append(f"Error processing skip {skip_id}: {e!s}")
            continue

    # Broadcast updated decided-action count
    if decided_actions:
        total = (
            db.execute(
                select(func.count())
                .select_from(Action)
                .where(Action.is_accepted.isnot(None))
            ).scalar()
            or 0
        )
        event_bus.notify(DecisionCountEvent(total=total), db)

    db.commit()

    # Apply accepted actions to Wikidata (don't rollback decisions on failure)
    apply_errors = []
    for action in accepted_actions:
        try:
            success = await apply_action(db, action, current_user.jwt_token)
        except (
            SQLAlchemyError,
            httpx2.HTTPError,
            ValueError,
            KeyError,
        ) as e:
            apply_errors.append(f"Error applying action {action.id}: {e!s}")
            continue
        if not success:
            apply_errors.append(
                f"Failed to apply action {action.id}"
                + (f": {action.error}" if action.error else "")
            )
    errors.extend(apply_errors)

    return PatchActionsResponse(
        success=True,
        message=f"Successfully processed {processed_count} items"
        + (f" ({len(apply_errors)} apply errors)" if apply_errors else ""),
        errors=errors,
    )


@router.post(
    "/{qid}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_source(
    qid: str,
    request: CreateSourceRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Add a source link to a politician. Creates a Source and
    processes it in the background (fetch + extract). Returns 202 immediately.
    """
    politician = (
        db.execute(select(Politician).where(Politician.wikidata_id == qid))
        .scalars()
        .first()
    )
    if not politician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Politician with QID {qid} not found",
        )

    # Create Source
    source = Source(
        url=request.url,
        user_id=str(current_user.user_id),
    )
    db.add(source)
    db.flush()
    politician.sources.append(source)
    db.commit()

    # process_source_task manages its own session
    asyncio.create_task(process_source_task(source.id, politician.id))

    return SourceResponse(
        id=source.id,
        url=source.url,
        status=source.status.value,
        language_qids=[],
    )

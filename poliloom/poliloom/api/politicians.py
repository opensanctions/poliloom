"""Politicians API endpoints."""

import asyncio
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db_session
from ..archiving import process_source_task, process_next_politician
from ..enrichment import (
    count_politicians_with_unevaluated,
    has_enrichable_politicians,
)
from ..search import SearchService
from ..models import (
    Source,
    SourceLanguage,
    Evaluation,
    Politician,
    Property,
    PropertyReference,
    PropertyType,
)
from ..sse import EvaluationCountEvent, notify
from ..wikidata_statement import create_entity, create_statement, push_evaluation
from .schemas import (
    AcceptPropertyItem,
    SourceResponse,
    CreatePoliticianRequest,
    CreatePoliticianResponse,
    CreatePropertyItem,
    CreateSourceRequest,
    EnrichmentMetadata,
    NextPoliticianResponse,
    PatchPropertiesRequest,
    PatchPropertiesResponse,
    PoliticianResponse,
    RejectPropertyItem,
    PropertyReferenceResponse,
    PropertyResponse,
)

from .auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()

# Map frontend property type strings (Wikidata P-IDs) to backend enum
PROPERTY_TYPE_MAP = {
    "P569": PropertyType.BIRTH_DATE,
    "P570": PropertyType.DEATH_DATE,
    "P19": PropertyType.BIRTHPLACE,
    "P39": PropertyType.POSITION,
    "P27": PropertyType.CITIZENSHIP,
}

# =============================================================================
# Helper function to build property responses
# =============================================================================


def build_politician_response(politician) -> PoliticianResponse:
    """Build PoliticianResponse from a politician entity."""

    property_responses = []
    for prop in politician.properties:
        entity_name = None
        if prop.entity and prop.entity_id:
            entity_name = prop.entity.name

        refs = []
        for ref in prop.property_references:
            refs.append(
                PropertyReferenceResponse(
                    id=ref.id,
                    source_id=str(ref.source_id),
                    supporting_quotes=ref.supporting_quotes,
                )
            )

        property_responses.append(
            PropertyResponse(
                id=prop.id,
                type=prop.type,
                value=prop.value,
                value_precision=prop.value_precision,
                entity_id=prop.entity_id,
                entity_name=entity_name,
                statement_id=prop.statement_id,
                qualifiers=prop.qualifiers_json,
                references=prop.references_json,
                sources=refs,
            )
        )

    return PoliticianResponse(
        id=politician.id,
        name=politician.name,
        wikidata_id=politician.wikidata_id,
        sources=[
            SourceResponse(
                id=s.id,
                url=s.url,
                content_hash=s.content_hash,
                fetch_timestamp=s.fetch_timestamp,
                status=s.status.value,
                error=s.error.value if s.error else None,
                http_status_code=s.http_status_code,
            )
            for s in politician.sources
        ],
        properties=property_responses,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=CreatePoliticianResponse)
async def create_politician(
    request: CreatePoliticianRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new politician in Wikidata and the local database.

    Creates a Wikidata entity with instance-of-human and occupation-politician
    base statements, then creates a local database record.
    """
    errors = []
    jwt_token = current_user.jwt_token

    # 1. Create the Wikidata entity
    try:
        wikidata_id = await create_entity(request.name, jwt_token=jwt_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Wikidata entity: {str(e)}",
        )

    # 2. Add instance-of: human (P31 → Q5) and occupation: politician (P106 → Q82955)
    base_statements = [
        ("P31", {"type": "value", "content": "Q5"}),
        ("P106", {"type": "value", "content": "Q82955"}),
    ]
    for prop_id, value in base_statements:
        try:
            await create_statement(wikidata_id, prop_id, value, jwt_token=jwt_token)
        except Exception as e:
            errors.append(f"Failed to add {prop_id} statement: {str(e)}")

    # 3. Create the Politician row in the local DB
    politician = Politician(name=request.name, wikidata_id=wikidata_id)
    db.add(politician)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error creating politician: {str(e)}",
        )

    return CreatePoliticianResponse(
        success=True,
        wikidata_id=wikidata_id,
        message=f"Created politician '{request.name}' ({wikidata_id})",
        errors=errors,
    )


@router.get("/next", response_model=NextPoliticianResponse)
async def get_next_politician(
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs",
    ),
    exclude_ids: Optional[List[str]] = Query(
        default=None,
        description="Exclude politicians with these Wikidata QIDs from results",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get the next unevaluated politician's ID for navigation.

    Lightweight endpoint — returns only the next politician's IDs, not full data.
    Triggers background enrichment if needed.
    """
    query = Politician.query_base()
    query = Politician.filter_by_unevaluated_properties(query, languages=languages)

    if countries:
        query = Politician.filter_by_countries(query, countries)

    if exclude_ids:
        query = query.where(Politician.wikidata_id.notin_(exclude_ids))

    # Only need id and wikidata_id
    query = query.order_by(func.random()).limit(1)

    politician = db.execute(query).scalars().first()

    # Trigger enrichment if unevaluated pool is running low
    min_threshold = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
    current_count = count_politicians_with_unevaluated(db, languages, countries)
    can_enrich = has_enrichable_politicians(db, languages, countries)

    if current_count < min_threshold and can_enrich:
        logger.info(
            f"Only {current_count} politicians with unevaluated properties (threshold: {min_threshold}), triggering enrichment"
        )
        asyncio.create_task(
            process_next_politician(
                languages=languages,
                countries=countries,
            )
        )

    meta = EnrichmentMetadata(
        has_enrichable_politicians=can_enrich,
        total_matching_filters=current_count,
    )

    if politician:
        return NextPoliticianResponse(
            wikidata_id=politician.wikidata_id,
            meta=meta,
        )

    return NextPoliticianResponse(meta=meta)


@router.get("/search", response_model=List[PoliticianResponse])
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
    Search politicians by name/label using semantic similarity.

    Returns matching politicians ranked by relevance with their properties.
    """
    search_service = SearchService()
    entity_ids = Politician.find_similar(q, search_service, limit=limit)
    if not entity_ids:
        return []

    # Preserve search ranking order
    ordering = case(
        {eid: idx for idx, eid in enumerate(entity_ids)},
        value=Politician.wikidata_id,
    )

    query = (
        Politician.query_base()
        .where(Politician.wikidata_id.in_(entity_ids))
        .order_by(ordering)
        .options(
            selectinload(
                Politician.properties.and_(Property.deleted_at.is_(None))
            ).options(
                selectinload(Property.entity),
                selectinload(Property.property_references),
            ),
        )
    )

    politicians = db.execute(query).scalars().all()

    return [build_politician_response(politician) for politician in politicians]


@router.get("/{qid}", response_model=PoliticianResponse)
async def get_politician(
    qid: str,
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter properties by language QIDs",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a single politician by Wikidata QID with all non-deleted properties.
    """
    query = Politician.query_base().where(Politician.wikidata_id == qid)

    if languages:
        # Filter properties: include Wikidata properties OR properties with matching language
        property_filter = and_(
            Property.deleted_at.is_(None),
            or_(
                Property.statement_id.isnot(None),
                exists(
                    select(1)
                    .select_from(PropertyReference)
                    .join(
                        SourceLanguage,
                        SourceLanguage.source_id == PropertyReference.source_id,
                    )
                    .where(
                        PropertyReference.property_id == Property.id,
                        SourceLanguage.language_id.in_(languages),
                    )
                ),
            ),
        )

        query = query.options(
            selectinload(Politician.properties.and_(property_filter)).options(
                selectinload(Property.entity),
                selectinload(Property.property_references),
            ),
            selectinload(Politician.sources),
        )
    else:
        query = query.options(
            selectinload(
                Politician.properties.and_(Property.deleted_at.is_(None))
            ).options(
                selectinload(Property.entity),
                selectinload(Property.property_references),
            ),
            selectinload(Politician.sources),
        )

    query = query.execution_options(populate_existing=True)

    politician = db.execute(query).scalars().first()

    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    return build_politician_response(politician)


async def process_property_actions(
    items_by_politician: dict[str, list],
    db: Session,
    current_user: User,
) -> PatchPropertiesResponse:
    """Shared evaluation logic for both politician and source endpoints.

    Args:
        items_by_politician: Property actions keyed by politician ID (UUID).
            Accept/reject items only need the property ID (politician key is
            for grouping only). Create items use the key to look up the politician.
    """
    errors = []
    all_evaluations = []

    # Batch-load all politicians needed for create actions
    from uuid import UUID as _UUID

    all_ids = set(items_by_politician.keys())
    politicians_by_id = {}
    if all_ids:
        uuid_ids = [_UUID(pid) for pid in all_ids]
        results = (
            db.execute(select(Politician).where(Politician.id.in_(uuid_ids)))
            .scalars()
            .all()
        )
        politicians_by_id = {str(p.id): p for p in results}

    for politician_id, items in items_by_politician.items():
        for item in items:
            try:
                match item:
                    case AcceptPropertyItem() | RejectPropertyItem():
                        property_entity = db.get(Property, item.id)
                        if not property_entity:
                            errors.append(f"Property {item.id} not found")
                            continue

                        evaluation = Evaluation(
                            user_id=str(current_user.user_id),
                            is_accepted=isinstance(item, AcceptPropertyItem),
                            property_id=item.id,
                        )
                        db.add(evaluation)
                        all_evaluations.append(evaluation)

                    case CreatePropertyItem():
                        prop_type = PROPERTY_TYPE_MAP.get(item.type)
                        if not prop_type:
                            errors.append(f"Unknown property type: {item.type}")
                            continue

                        politician = politicians_by_id.get(politician_id)
                        if not politician:
                            errors.append(f"Politician {politician_id} not found")
                            continue

                        new_property = Property(
                            politician_id=politician.id,
                            type=prop_type,
                            value=item.value,
                            value_precision=item.value_precision,
                            entity_id=item.entity_id,
                            qualifiers_json=item.qualifiers,
                        )
                        db.add(new_property)
                        db.flush()

                        evaluation = Evaluation(
                            user_id=str(current_user.user_id),
                            is_accepted=True,
                            property_id=new_property.id,
                        )
                        db.add(evaluation)
                        all_evaluations.append(evaluation)

            except Exception as e:
                item_desc = str(
                    getattr(item, "id", None) or f"new {getattr(item, 'type', '?')}"
                )
                errors.append(f"Error processing item {item_desc}: {str(e)}")
                continue

    db.commit()

    # Broadcast updated evaluation count
    if all_evaluations:
        total = db.execute(select(func.count()).select_from(Evaluation)).scalar() or 0
        notify(EvaluationCountEvent(total=total))

    # Push evaluations to Wikidata (don't rollback local changes on failure)
    wikidata_errors = []

    jwt_token = current_user.jwt_token
    if not jwt_token:
        wikidata_errors.append("No JWT token available for Wikidata API calls")
    else:
        for evaluation in all_evaluations:
            try:
                success = await push_evaluation(evaluation, jwt_token, db)
                if not success:
                    wikidata_errors.append(
                        f"Failed to process evaluation {evaluation.id} in Wikidata"
                    )
            except Exception as e:
                wikidata_errors.append(
                    f"Error processing evaluation {evaluation.id} in Wikidata: {str(e)}"
                )

    if wikidata_errors:
        errors.extend(wikidata_errors)

    return PatchPropertiesResponse(
        success=True,
        message=f"Successfully processed {len(all_evaluations)} items"
        + (f" ({len(wikidata_errors)} Wikidata errors)" if wikidata_errors else ""),
        errors=errors,
    )


@router.patch("/{qid}/properties", response_model=PatchPropertiesResponse)
async def patch_properties(
    qid: str,
    request: PatchPropertiesRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Accept, reject, or create properties for a politician.

    Each item must specify an explicit `action`:
    - `accept` / `reject`: evaluate an existing property (requires `id`)
    - `create`: add a new property (requires `type` + value/entity fields)
    """
    # Verify politician exists
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

    return await process_property_actions(
        {str(politician.id): request.items}, db, current_user
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
    Add a source link to a politician. Creates a pending Source and
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

    # Create pending Source
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
    )

"""Politicians API endpoints."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db_session
from ..enrichment import (
    count_politicians_with_unevaluated,
    enrich_batch,
    has_enrichable_politicians,
)
from ..search import SearchService
from ..models import (
    ArchivedPage,
    ArchivedPageLanguage,
    Evaluation,
    Politician,
    Property,
    PropertyReference,
    PropertyType,
)
from ..wikidata_statement import push_evaluation
from .schemas import (
    AcceptPropertyItem,
    ArchivedPageResponse,
    CreatePropertyItem,
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

# Thread pool for background enrichment tasks (4 concurrent workers)
_enrichment_executor = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="enrichment"
)


# =============================================================================
# Helper function to build property responses
# =============================================================================


def build_property_responses(properties) -> List[PropertyResponse]:
    """Build PropertyResponse list from property entities."""
    responses = []
    for prop in properties:
        entity_name = None
        if prop.entity and prop.entity_id:
            entity_name = prop.entity.name

        # Build sources from PropertyReferences
        sources = []
        for ref in prop.property_references:
            sources.append(
                PropertyReferenceResponse(
                    id=ref.id,
                    archived_page=ArchivedPageResponse(
                        id=ref.archived_page.id,
                        url=ref.archived_page.url,
                        content_hash=ref.archived_page.content_hash,
                        fetch_timestamp=ref.archived_page.fetch_timestamp,
                    ),
                    supporting_quotes=ref.supporting_quotes,
                )
            )

        responses.append(
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
                sources=sources,
            )
        )
    return responses


def _trigger_enrichment_if_needed(
    db: Session,
    languages: Optional[List[str]],
    countries: Optional[List[str]],
) -> EnrichmentMetadata:
    """Check enrichment status and trigger background enrichment if needed.

    Returns EnrichmentMetadata with current status.
    """
    min_threshold = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
    current_count = count_politicians_with_unevaluated(db, languages, countries)
    can_enrich = has_enrichable_politicians(db, languages, countries)

    if current_count < min_threshold and can_enrich:
        logger.info(
            f"Only {current_count} politicians with unevaluated properties (threshold: {min_threshold}), triggering enrichment batch"
        )
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            _enrichment_executor,
            enrich_batch,
            languages,
            countries,
        )

    return EnrichmentMetadata(
        has_enrichable_politicians=can_enrich,
        total_matching_filters=current_count,
    )


# =============================================================================
# Endpoints
# =============================================================================


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

    meta = _trigger_enrichment_if_needed(db, languages, countries)

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
                selectinload(Property.property_references).selectinload(
                    PropertyReference.archived_page
                ),
            ),
        )
    )

    politicians = db.execute(query).scalars().all()

    return [
        PoliticianResponse(
            id=politician.id,
            name=politician.name,
            wikidata_id=politician.wikidata_id,
            properties=build_property_responses(politician.properties),
        )
        for politician in politicians
    ]


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
                        ArchivedPageLanguage,
                        ArchivedPageLanguage.archived_page_id
                        == PropertyReference.archived_page_id,
                    )
                    .where(
                        PropertyReference.property_id == Property.id,
                        ArchivedPageLanguage.language_id.in_(languages),
                    )
                ),
            ),
        )

        query = query.options(
            selectinload(Politician.properties.and_(property_filter)).options(
                selectinload(Property.entity),
                selectinload(Property.property_references)
                .selectinload(PropertyReference.archived_page)
                .selectinload(ArchivedPage.language_entities),
            ),
            selectinload(Politician.wikipedia_links),
        )
    else:
        query = query.options(
            selectinload(
                Politician.properties.and_(Property.deleted_at.is_(None))
            ).options(
                selectinload(Property.entity),
                selectinload(Property.property_references)
                .selectinload(PropertyReference.archived_page)
                .selectinload(ArchivedPage.language_entities),
            ),
            selectinload(Politician.wikipedia_links),
        )

    query = query.execution_options(populate_existing=True)

    politician = db.execute(query).scalars().first()

    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    return PoliticianResponse(
        id=politician.id,
        name=politician.name,
        wikidata_id=politician.wikidata_id,
        properties=build_property_responses(politician.properties),
    )


async def process_property_actions(
    items_by_politician: dict[str, list],
    db: Session,
    current_user: User,
) -> PatchPropertiesResponse:
    """Shared evaluation logic for both politician and source endpoints.

    Args:
        items_by_politician: Property actions keyed by politician QID.
            Accept/reject items only need the property ID (politician key is
            for grouping only). Create items use the key to look up the politician.
    """
    errors = []
    all_evaluations = []

    # Batch-load all politicians needed for create actions
    all_qids = set(items_by_politician.keys())
    politicians_by_qid = {}
    if all_qids:
        results = (
            db.execute(select(Politician).where(Politician.wikidata_id.in_(all_qids)))
            .scalars()
            .all()
        )
        politicians_by_qid = {p.wikidata_id: p for p in results}

    for qid, items in items_by_politician.items():
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

                        politician = politicians_by_qid.get(qid)
                        if not politician:
                            errors.append(f"Politician with QID {qid} not found")
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

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

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

    return await process_property_actions({qid: request.items}, db, current_user)

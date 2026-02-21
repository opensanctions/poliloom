"""Politicians API endpoints."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    Politician,
    Property,
    PropertyReference,
)
from .schemas import (
    ArchivedPageResponse,
    EnrichmentMetadata,
    NextPoliticianResponse,
    PoliticianResponse,
    PropertyReferenceResponse,
    PropertyResponse,
)
from .auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()

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

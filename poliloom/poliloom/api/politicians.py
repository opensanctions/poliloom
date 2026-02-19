"""Politicians API endpoints."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
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
    PoliticianResponse,
    PoliticiansListResponse,
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


# =============================================================================
# List and Search Endpoints
# =============================================================================


@router.get("", response_model=PoliticiansListResponse)
async def get_politicians(
    limit: int = Query(
        default=2, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of politicians to skip"),
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs - politicians with properties from archived pages with matching language",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs - politicians with citizenship for these countries",
    ),
    exclude_ids: Optional[List[str]] = Query(
        default=None,
        description="Exclude politicians with these UUIDs from results (for avoiding duplicates during navigation)",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians with unevaluated extracted data for review and evaluation.

    Returns a list of politicians that have properties without statement_id (unevaluated).
    Automatically triggers background enrichment if the number of politicians with
    unevaluated properties falls below MIN_UNEVALUATED_POLITICIANS (default: 10).

    Response includes metadata about enrichment status for UI empty states.
    """
    # Build composable politician query
    query = Politician.query_base()

    # Always filter for unevaluated properties
    query = Politician.filter_by_unevaluated_properties(query, languages=languages)

    if countries:
        query = Politician.filter_by_countries(query, countries)

    # Exclude specific politician IDs (for avoiding duplicates during navigation)
    if exclude_ids:
        try:
            exclude_uuids = [UUID(id_str) for id_str in exclude_ids]
            query = query.where(Politician.id.notin_(exclude_uuids))
        except ValueError:
            # Invalid UUID format - log and ignore
            logger.warning(f"Invalid UUID format in exclude_ids: {exclude_ids}")

    # Load related data
    if languages:
        # Filter properties: include Wikidata properties OR properties with matching language
        property_filter = and_(
            Property.deleted_at.is_(None),
            or_(
                # Include Wikidata properties (have statement_id)
                Property.statement_id.isnot(None),
                # Include properties where any PropertyReference's archived page has matching language
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
        # No language filter, load all properties
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

    # Random ordering for variety
    query = query.order_by(func.random())

    # Apply offset and limit
    query = query.offset(offset).limit(limit)

    # Apply populate_existing to ensure fresh property loads when using .and_() filters
    query = query.execution_options(populate_existing=True)

    # Execute query
    politicians = db.execute(query).scalars().all()

    # Track enrichment status for empty state UX
    min_threshold = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
    current_count = count_politicians_with_unevaluated(db, languages, countries)

    # Check if there are politicians available to enrich (for "all caught up" state)
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

    result = []
    for politician in politicians:
        result.append(
            PoliticianResponse(
                id=politician.id,
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                properties=build_property_responses(politician.properties),
            )
        )

    return PoliticiansListResponse(
        politicians=result,
        meta=EnrichmentMetadata(
            has_enrichable_politicians=can_enrich,
            total_matching_filters=current_count,
        ),
    )


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

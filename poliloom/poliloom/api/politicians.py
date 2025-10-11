"""Politicians API endpoints."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_, or_, func

from ..database import get_engine
from ..models import (
    Politician,
    Property,
    ArchivedPage,
    Language,
    WikidataEntity,
    WikidataEntityLabel,
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
)
from .auth import get_current_user, User
from ..enrichment import enrich_until_target

router = APIRouter()

# Thread pool for background enrichment tasks (single worker)
_enrichment_executor = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="enrichment"
)

# Track the current enrichment task future
_enrichment_future = None


@router.get("", response_model=List[PoliticianResponse])
async def get_politicians(
    limit: int = Query(
        default=2, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of politicians to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search politicians by name/label using fuzzy matching",
    ),
    has_unevaluated: Optional[bool] = Query(
        default=None,
        description="Filter to only politicians with unevaluated properties. If not specified, returns all politicians.",
    ),
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs - politicians with properties from archived pages with matching iso1_code or iso3_code",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs - politicians with citizenship for these countries",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians that have unevaluated extracted data.

    Returns a list of politicians with their Wikidata properties, positions, birthplaces
    and unevaluated extracted data for review and evaluation.

    Automatically triggers background enrichment if the number of politicians with
    unevaluated properties falls below MIN_UNEVALUATED_POLITICIANS (default: 10).
    """
    with Session(get_engine()) as db:
        # Build composable politician query
        query = Politician.query_base()

        # Apply filters
        if search:
            query = Politician.search_by_label(query, search)

        if has_unevaluated is True:
            query = Politician.filter_by_unevaluated_properties(
                query, languages=languages
            )
        elif has_unevaluated is False:
            # Explicitly filter for politicians WITH evaluated properties
            # (inverse of unevaluated filter) - currently not implemented
            # For now, has_unevaluated=false returns all politicians
            pass

        if countries:
            query = Politician.filter_by_countries(query, countries)

        # Load related data with selectinload
        if languages:
            # When language filter is active, we need to filter properties
            query = query.options(
                selectinload(
                    Politician.properties.and_(
                        and_(
                            Property.deleted_at.is_(
                                None
                            ),  # Exclude soft-deleted properties
                            or_(
                                Property.archived_page_id.is_(
                                    None
                                ),  # Include Wikidata properties
                                Property.archived_page.has(
                                    ArchivedPage.iso1_code.in_(
                                        select(Language.iso1_code).where(
                                            Language.wikidata_id.in_(languages)
                                        )
                                    )
                                )
                                | Property.archived_page.has(
                                    ArchivedPage.iso3_code.in_(
                                        select(Language.iso3_code).where(
                                            Language.wikidata_id.in_(languages)
                                        )
                                    )
                                ),
                            ),
                        )
                    )
                ).options(
                    selectinload(Property.entity),
                    selectinload(Property.archived_page),
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
                    selectinload(Property.archived_page),
                ),
                selectinload(Politician.wikipedia_links),
            )

        # Apply random ordering if not searching (search already orders by similarity)
        if not search:
            query = query.order_by(func.random())

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        politicians = db.execute(query).scalars().all()

        # Trigger background enrichment when filtering for unevaluated
        if has_unevaluated is True:
            global _enrichment_future

            # Only start a new enrichment job if none is currently running
            if _enrichment_future is None or _enrichment_future.done():
                min_unevaluated = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
                # Run enrichment in separate thread to avoid blocking API workers
                loop = asyncio.get_running_loop()
                _enrichment_future = loop.run_in_executor(
                    _enrichment_executor,
                    enrich_until_target,
                    min_unevaluated,
                    languages,
                    countries,
                )

        if not politicians:
            return []

        result = []
        for politician in politicians:
            property_responses = []
            for prop in politician.properties:
                # Add entity name if applicable
                entity_name = None
                if prop.entity and prop.entity_id:
                    entity_name = prop.entity.name

                property_responses.append(
                    PropertyResponse(
                        id=prop.id,
                        type=prop.type,
                        value=prop.value,
                        value_precision=prop.value_precision,
                        entity_id=prop.entity_id,
                        entity_name=entity_name,
                        proof_line=prop.proof_line,
                        statement_id=prop.statement_id,
                        qualifiers=prop.qualifiers_json,
                        references=prop.references_json,
                        archived_page=(
                            ArchivedPageResponse(
                                id=prop.archived_page.id,
                                url=prop.archived_page.url,
                                content_hash=prop.archived_page.content_hash,
                                fetch_timestamp=prop.archived_page.fetch_timestamp,
                            )
                            if prop.archived_page
                            else None
                        ),
                    )
                )

            result.append(
                PoliticianResponse(
                    id=politician.id,
                    name=politician.name,
                    wikidata_id=politician.wikidata_id,
                    properties=property_responses,
                )
            )

    return result

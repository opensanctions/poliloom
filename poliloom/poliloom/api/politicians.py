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
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
)
from .auth import get_current_user, User
from ..enrichment import enrich_until_target

router = APIRouter()

# Thread pool for background enrichment tasks
_enrichment_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="enrichment"
)


@router.get("", response_model=List[PoliticianResponse])
async def get_politicians(
    limit: int = Query(
        default=2, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of politicians to skip"),
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

    Filters:
    - languages: List of language QIDs. Returns only properties from archived pages
      with matching iso1_code or iso3_code. Politicians are included only if they have
      at least one property matching the language filter.
    - countries: List of country QIDs. Filters for politicians that have citizenship
      for these countries.

    Environment variables:
        MIN_UNEVALUATED_POLITICIANS: Minimum number of politicians with unevaluated
                                     properties before triggering enrichment (default: 10)
    """
    with Session(get_engine()) as db:
        # Use the shared query logic from Politician model
        politician_ids_query = Politician.query_with_unevaluated_properties(
            languages=languages, countries=countries
        )

        # Now build the main query to fetch politicians with their data
        # Add window function to get total count without separate query
        query = select(Politician, func.count().over().label("total_count")).where(
            Politician.id.in_(politician_ids_query)
        )

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

        # Deterministic ordering is great if we have low candidate pool of
        # enriched politicians, however, it does not allow us to skip
        # politicians, as we will always be served the same one.

        # Set random seed based on user_id for consistent random ordering per user
        # Using modulo to keep seed value within PostgreSQL's valid range (0.0 to 1.0)
        # seed_value = (current_user.user_id % 1000000) / 1000000.0
        # db.execute(text(f"SELECT setseed({seed_value})"))

        # Apply random ordering, offset, and limit
        query = query.order_by(func.random()).offset(offset).limit(limit)

        # Execute query
        rows = db.execute(query).all()

        # Extract politicians and total count
        if rows:
            politicians = [row[0] for row in rows]
            total_count = rows[0][1]
        else:
            politicians = []
            total_count = 0

        # Trigger background enrichment if below threshold
        min_unevaluated = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
        if total_count < min_unevaluated:
            # Run enrichment in separate thread to avoid blocking API workers
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
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

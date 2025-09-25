"""Politicians API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_, or_, func

from ..database import get_engine
from ..models import (
    Politician,
    Property,
    ArchivedPage,
    PropertyType,
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
)
from .auth import get_current_user, User

router = APIRouter()


@router.get("/", response_model=List[PoliticianResponse])
async def get_politicians(
    limit: int = Query(
        default=50, le=100, description="Maximum number of politicians to return"
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

    Filters:
    - languages: List of language QIDs. Filters for politicians that have extracted
      properties from archived pages with matching iso1_code or iso3_code.
    - countries: List of country QIDs. Filters for politicians that have citizenship
      for these countries.
    """
    with Session(get_engine()) as db:
        # Build the base query for politicians that need evaluation
        base_query = (
            select(Politician.id)
            .join(Property, Politician.id == Property.politician_id)
            .where(Property.statement_id.is_(None))
        )

        # Apply language filtering if provided
        if languages:
            from ..models import Language

            # Join with archived pages and then with languages table
            # Match on iso1_code or iso3_code
            base_query = (
                base_query.join(
                    ArchivedPage, Property.archived_page_id == ArchivedPage.id
                )
                .join(
                    Language,
                    or_(
                        ArchivedPage.iso1_code == Language.iso1_code,
                        ArchivedPage.iso3_code == Language.iso3_code,
                    ),
                )
                .where(Language.wikidata_id.in_(languages))
            )

        # Apply country filtering if provided
        if countries:
            citizenship_subquery = select(Property.politician_id).where(
                and_(
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.in_(countries),
                )
            )
            base_query = base_query.where(Politician.id.in_(citizenship_subquery))

        # Apply randomization and limit (offset doesn't make sense with random ordering)
        # Need to use subquery to apply DISTINCT before ordering by random
        distinct_subquery = base_query.distinct().subquery()
        final_query = (
            select(distinct_subquery.c.id).order_by(func.random()).limit(limit)
        )

        # Get politician IDs that need evaluation with filters applied
        result = db.execute(final_query)
        politician_ids = [row[0] for row in result]

        if not politician_ids:
            return []

        # Now fetch the full politician objects with relationships
        query = (
            select(Politician)
            .options(
                selectinload(Politician.properties).options(
                    selectinload(Property.entity),
                    selectinload(Property.archived_page),
                ),
                selectinload(Politician.wikipedia_links),
            )
            .where(Politician.id.in_(politician_ids))
        )

        politicians = db.execute(query).scalars().all()

        result = []
        for politician in politicians:
            # Simplified response building - no grouping
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

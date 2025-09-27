"""Politicians API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_, or_, func

from ..models import Language

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


@router.get("", response_model=List[PoliticianResponse])
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
    - languages: List of language QIDs. Returns only properties from archived pages
      with matching iso1_code or iso3_code. Politicians are included only if they have
      at least one property matching the language filter.
    - countries: List of country QIDs. Filters for politicians that have citizenship
      for these countries.
    """
    with Session(get_engine()) as db:
        # First, find politician IDs that have unevaluated properties
        politician_ids_query = (
            select(Politician.id.distinct())
            .join(Property)
            .where(and_(Property.statement_id.is_(None), Property.deleted_at.is_(None)))
        )

        # Apply language filtering
        if languages:
            politician_ids_query = (
                politician_ids_query.join(
                    ArchivedPage, Property.archived_page_id == ArchivedPage.id
                )
                .join(
                    Language,
                    or_(
                        and_(
                            ArchivedPage.iso1_code.isnot(None),
                            ArchivedPage.iso1_code == Language.iso1_code,
                        ),
                        and_(
                            ArchivedPage.iso3_code.isnot(None),
                            ArchivedPage.iso3_code == Language.iso3_code,
                        ),
                    ),
                )
                .where(Language.wikidata_id.in_(languages))
            )

        # Apply country filtering
        if countries:
            citizenship_subquery = select(Property.politician_id).where(
                and_(
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.in_(countries),
                )
            )
            politician_ids_query = politician_ids_query.where(
                Politician.id.in_(citizenship_subquery)
            )

        # Now build the main query to fetch politicians with their data
        query = select(Politician).where(Politician.id.in_(politician_ids_query))

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

        # Set random seed based on user_id for consistent random ordering per user
        # Using modulo to keep seed value within PostgreSQL's valid range (0.0 to 1.0)
        # seed_value = (current_user.user_id % 1000000) / 1000000.0
        # db.execute(text(f"SELECT setseed({seed_value})"))

        # Apply random ordering and limit
        query = query.order_by(func.random()).limit(limit)

        # Execute query
        politicians = db.execute(query).scalars().all()

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

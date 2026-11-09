"""API endpoints for entities like languages and countries."""

from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import (
    Country,
    Language,
    Location,
    Position,
    Statement,
    WikidataEntity,
    WikipediaLink,
    WikipediaProject,
)
from ..models.base import RelationType
from ..models.statement import active_citizenship_conditions
from ..models.wikidata import WikidataRelation
from .auth import User, get_current_user
from .schemas import (
    CountryResponse,
    EntitySearchResponse,
    LanguageResponse,
    TermMaps,
)

router = APIRouter()


# =============================================================================
# List Endpoints - Fast, flat data for filter dropdowns
# =============================================================================


@router.get("/languages", response_model=list[LanguageResponse])
async def get_languages(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve languages with source counts for filter dropdowns.

    Only languages with at least one linked source are returned. The counts are
    aggregated separately from the term maps: grouping over the term columns
    would hash every language's full term maps once per link row.
    """
    counts = (
        select(
            WikidataRelation.parent_entity_id.label("language_id"),
            func.count(WikipediaLink.id).label("sources_count"),
        )
        .join(
            WikipediaProject,
            and_(
                WikipediaProject.wikidata_id == WikidataRelation.child_entity_id,
                WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
            ),
        )
        .join(
            WikipediaLink,
            WikipediaLink.wikipedia_project_id == WikipediaProject.wikidata_id,
        )
        .group_by(WikidataRelation.parent_entity_id)
        .subquery()
    )

    query = (
        select(
            Language.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
            Language.wikimedia_code,
            Language.iso_639_1,
            Language.iso_639_3,
            counts.c.sources_count,
        )
        .select_from(Language)
        .join(
            WikidataEntity,
            Language.wikidata_id == WikidataEntity.wikidata_id,
        )
        .join(
            counts,
            counts.c.language_id == Language.wikidata_id,
        )
        .order_by(counts.c.sources_count.desc())
    )

    results = db.execute(query).all()

    return [
        LanguageResponse(
            wikidata_id=row.wikidata_id,
            terms=TermMaps(
                labels=row.labels,
                descriptions=row.descriptions,
                aliases=row.aliases,
            ),
            wikimedia_code=row.wikimedia_code,
            iso_639_1=row.iso_639_1,
            iso_639_3=row.iso_639_3,
            sources_count=row.sources_count,
        )
        for row in results
    ]


@router.get("/countries", response_model=list[CountryResponse])
async def get_countries(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all countries with citizenship counts for filter dropdowns.

    The citizenship count is the number of live P27 citizenship statements
    pointing at the country. Returns a flat list ordered by citizenship count.
    For searching countries, use /countries/search.

    The counts are aggregated separately from the term maps: grouping over the
    term columns would hash every country's full term maps once per statement.
    """
    counts = (
        select(
            Statement.entity_id.label("country_id"),
            func.count(Statement.id).label("citizenships_count"),
        )
        .where(*active_citizenship_conditions(Statement))
        .group_by(Statement.entity_id)
        .subquery()
    )

    query = (
        select(
            Country.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
            counts.c.citizenships_count,
        )
        .select_from(Country)
        .join(
            WikidataEntity,
            Country.wikidata_id == WikidataEntity.wikidata_id,
        )
        .join(
            counts,
            counts.c.country_id == Country.wikidata_id,
        )
        .order_by(counts.c.citizenships_count.desc())
    )

    results = db.execute(query).all()

    return [
        CountryResponse(
            wikidata_id=row.wikidata_id,
            terms=TermMaps(
                labels=row.labels,
                descriptions=row.descriptions,
                aliases=row.aliases,
            ),
            citizenships_count=row.citizenships_count,
        )
        for row in results
    ]


# =============================================================================
# Search Endpoints - With hierarchy/descriptions for entity selection
# =============================================================================


class EntityType(str, Enum):
    position = "position"
    location = "location"
    country = "country"


ENTITY_TYPE_MODELS: dict[EntityType, type] = {
    EntityType.position: Position,
    EntityType.location: Location,
    EntityType.country: Country,
}


@router.get("/entities/search", response_model=list[EntitySearchResponse])
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    type: EntityType = Query(..., description="Entity type"),
    limit: int = Query(default=50, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Search entities by label or alias."""
    model_class = ENTITY_TYPE_MODELS[type]

    entity_ids = model_class.find_similar(q, limit=limit)
    if not entity_ids:
        return []

    ordering = case(
        {eid: idx for idx, eid in enumerate(entity_ids)},
        value=model_class.wikidata_id,
    )

    query = (
        select(model_class)
        .join(
            WikidataEntity,
            model_class.wikidata_id == WikidataEntity.wikidata_id,
        )
        .where(model_class.wikidata_id.in_(entity_ids))
        .order_by(ordering)
    )

    entities = db.execute(query).scalars().all()
    return [
        EntitySearchResponse(
            wikidata_id=e.wikidata_id,
            terms=TermMaps.from_entity(e.wikidata_entity),
        )
        for e in entities
    ]

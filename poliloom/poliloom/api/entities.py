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


def _term_maps(entity: WikidataEntity) -> TermMaps:
    """Build TermMaps from a WikidataEntity's language-keyed term columns."""
    return TermMaps(
        labels=entity.labels,
        descriptions=entity.descriptions,
        aliases=entity.aliases,
    )


# =============================================================================
# List Endpoints - Fast, flat data for filter dropdowns
# =============================================================================


@router.get("/languages", response_model=list[LanguageResponse])
async def get_languages(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all languages with source counts for filter dropdowns.

    Returns a flat list of languages ordered by number of sources.
    """
    query = (
        select(
            Language.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
            Language.wikimedia_code,
            Language.iso_639_1,
            Language.iso_639_3,
            func.count(WikipediaLink.id).label("sources_count"),
        )
        .select_from(Language)
        .join(
            WikidataEntity,
            Language.wikidata_id == WikidataEntity.wikidata_id,
        )
        .join(
            WikidataRelation,
            and_(
                WikidataRelation.parent_entity_id == Language.wikidata_id,
                WikidataRelation.deleted_at.is_(None),
            ),
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
        .where(WikidataEntity.deleted_at.is_(None))
        .group_by(
            Language.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
            Language.wikimedia_code,
            Language.iso_639_1,
            Language.iso_639_3,
        )
        .order_by(func.count(WikipediaLink.id).desc())
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
    """
    query = (
        select(
            Country.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
            func.count(Statement.id).label("citizenships_count"),
        )
        .select_from(Country)
        .join(
            WikidataEntity,
            Country.wikidata_id == WikidataEntity.wikidata_id,
        )
        .join(
            Statement,
            and_(
                Statement.entity_id == Country.wikidata_id,
                *active_citizenship_conditions(Statement),
            ),
        )
        .where(WikidataEntity.deleted_at.is_(None))
        .group_by(
            Country.wikidata_id,
            WikidataEntity.labels,
            WikidataEntity.descriptions,
            WikidataEntity.aliases,
        )
        .order_by(func.count(Statement.id).desc())
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
        .where(WikidataEntity.deleted_at.is_(None))
        .where(model_class.wikidata_id.in_(entity_ids))
        .order_by(ordering)
    )

    entities = db.execute(query).scalars().all()
    return [
        EntitySearchResponse(
            wikidata_id=e.wikidata_id,
            terms=_term_maps(e.wikidata_entity),
        )
        for e in entities
    ]

"""API endpoints for entities like languages and countries."""

from enum import Enum
from typing import List, Type
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, case

from ..database import get_db_session
from ..search import SearchService
from ..models import (
    Language,
    Country,
    Position,
    Location,
    WikidataEntity,
    WikipediaLink,
    WikipediaProject,
    Property,
)
from ..models.wikidata import WikidataRelation
from ..models.base import PropertyType, RelationType
from .schemas import (
    LanguageResponse,
    CountryResponse,
    EntitySearchResponse,
)
from .auth import get_current_user, User

router = APIRouter()


# =============================================================================
# List Endpoints - Fast, flat data for filter dropdowns
# =============================================================================


@router.get("/languages", response_model=List[LanguageResponse])
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
            WikidataEntity.name,
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
            WikidataEntity.name,
            Language.iso_639_1,
            Language.iso_639_3,
        )
        .order_by(func.count(WikipediaLink.id).desc())
    )

    results = db.execute(query).all()

    return [
        LanguageResponse(
            wikidata_id=row.wikidata_id,
            name=row.name,
            iso_639_1=row.iso_639_1,
            iso_639_3=row.iso_639_3,
            sources_count=row.sources_count,
        )
        for row in results
    ]


@router.get("/countries", response_model=List[CountryResponse])
async def get_countries(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all countries with citizenship counts for filter dropdowns.

    Returns a flat list of countries ordered by number of citizenships.
    For searching countries, use /countries/search.
    """
    query = (
        select(
            Country.wikidata_id,
            WikidataEntity.name,
            func.count(Property.id).label("citizenships_count"),
        )
        .select_from(Country)
        .join(
            WikidataEntity,
            Country.wikidata_id == WikidataEntity.wikidata_id,
        )
        .join(
            Property,
            and_(
                Property.entity_id == Country.wikidata_id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.deleted_at.is_(None),
            ),
        )
        .where(WikidataEntity.deleted_at.is_(None))
        .group_by(Country.wikidata_id, WikidataEntity.name)
        .order_by(func.count(Property.id).desc())
    )

    results = db.execute(query).all()

    return [
        CountryResponse(
            wikidata_id=row.wikidata_id,
            name=row.name,
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


ENTITY_TYPE_MODELS: dict[EntityType, Type] = {
    EntityType.position: Position,
    EntityType.location: Location,
    EntityType.country: Country,
}


@router.get("/entities/search", response_model=List[EntitySearchResponse])
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    type: EntityType = Query(..., description="Entity type"),
    limit: int = Query(default=50, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Search entities by name/label using semantic similarity."""
    model_class = ENTITY_TYPE_MODELS[type]

    search_service = SearchService()
    entity_ids = model_class.find_similar(q, search_service, limit=limit)
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
        .options(
            selectinload(model_class.wikidata_entity)
            .selectinload(
                WikidataEntity.parent_relations.and_(
                    WikidataRelation.deleted_at.is_(None)
                )
            )
            .selectinload(WikidataRelation.parent_entity)
        )
    )

    entities = db.execute(query).scalars().all()
    return [
        EntitySearchResponse(
            wikidata_id=e.wikidata_id,
            name=e.name,
            description=e.description,
        )
        for e in entities
    ]

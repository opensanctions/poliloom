"""API endpoints for entities like languages and countries."""

from typing import List, Type, Callable
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
    PositionResponse,
    LocationResponse,
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
            WikidataRelation.parent_entity_id == Language.wikidata_id,
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


def create_search_endpoint(
    model_class: Type,
    response_mapper: Callable,
):
    """
    Factory function to create a search endpoint with required q parameter.

    Args:
        model_class: The SQLAlchemy model class (e.g., Country, Position)
        response_mapper: Function to map model instance to response schema
    """
    entity_name = model_class.__tablename__

    async def endpoint(
        q: str = Query(
            ...,
            min_length=1,
            description=f"Search query for {entity_name}",
        ),
        limit: int = Query(
            default=50,
            le=100,
            description=f"Maximum number of {entity_name} to return",
        ),
        db: Session = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ):
        f"""
        Search {entity_name} by name/label using semantic similarity.

        Returns matching {entity_name} ranked by relevance with hierarchy data.
        """
        search_service = SearchService()
        entity_ids = model_class.find_similar(q, search_service, limit=limit)
        if not entity_ids:
            return []

        # Preserve search ranking order
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
                .selectinload(WikidataEntity.parent_relations)
                .selectinload(WikidataRelation.parent_entity)
            )
        )

        entities = db.execute(query).scalars().all()
        return [response_mapper(entity) for entity in entities]

    return endpoint


search_countries = router.get(
    "/countries/search", response_model=List[CountryResponse]
)(
    create_search_endpoint(
        model_class=Country,
        response_mapper=lambda country: CountryResponse(
            wikidata_id=country.wikidata_id,
            name=country.name,
            description=country.description,
            iso_code=country.iso_code,
            citizenships_count=0,
        ),
    )
)

search_positions = router.get(
    "/positions/search", response_model=List[PositionResponse]
)(
    create_search_endpoint(
        model_class=Position,
        response_mapper=lambda position: PositionResponse(
            wikidata_id=position.wikidata_id,
            name=position.name,
            description=position.description,
        ),
    )
)

search_locations = router.get(
    "/locations/search", response_model=List[LocationResponse]
)(
    create_search_endpoint(
        model_class=Location,
        response_mapper=lambda location: LocationResponse(
            wikidata_id=location.wikidata_id,
            name=location.name,
            description=location.description,
        ),
    )
)

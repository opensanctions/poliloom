"""API endpoints for entities like languages and countries."""

from typing import List, Optional, Type, Callable
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_

from ..database import get_db_session
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


def create_entity_endpoint(
    model_class: Type,
    response_mapper: Callable,
    entity_name: str,
):
    """
    Factory function to create a generic entity endpoint with search, limit, and offset support.

    Args:
        model_class: The SQLAlchemy model class (e.g., Country, Position)
        response_mapper: Function to map model instance to response schema
        entity_name: Name of the entity (plural) for documentation
    """

    async def endpoint(
        limit: int = Query(
            default=100,
            le=1000,
            description=f"Maximum number of {entity_name} to return",
        ),
        offset: int = Query(
            default=0, ge=0, description=f"Number of {entity_name} to skip"
        ),
        search: Optional[str] = Query(
            default=None,
            description=f"Search {entity_name} by name/label using fuzzy matching",
        ),
        db: Session = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ):
        f"""
        Retrieve {entity_name} with optional search filtering.

        Returns a list of {entity_name} with their metadata.
        Supports fuzzy text search on labels.
        """
        # Build base query filtering out soft-deleted entities
        query = (
            select(model_class)
            .join(
                WikidataEntity,
                model_class.wikidata_id == WikidataEntity.wikidata_id,
            )
            .where(WikidataEntity.deleted_at.is_(None))
        )

        # Add eager loading for wikidata_entity with parent_relations and their parent entities
        query = query.options(
            selectinload(model_class.wikidata_entity)
            .selectinload(WikidataEntity.parent_relations)
            .selectinload(WikidataRelation.parent_entity)
        )

        # Apply search filter if provided
        if search:
            query = model_class.search_by_label(query, search)

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        entities = db.execute(query).scalars().all()

        return [response_mapper(entity) for entity in entities]

    return endpoint


# Simple endpoints for reference data (languages and countries)
@router.get("/languages", response_model=List[LanguageResponse])
async def get_languages(
    limit: int = Query(
        default=100,
        le=1000,
        description="Maximum number of languages to return",
    ),
    offset: int = Query(default=0, ge=0, description="Number of languages to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search languages by name/label using fuzzy matching",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all languages with source counts.

    Returns a list of all languages with their metadata and the count of
    sources (currently Wikipedia links) using each language via Wikipedia projects.
    """
    # Direct query with grouping - no subquery needed
    query = (
        select(
            Language,
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
        .group_by(Language.wikidata_id)
        .order_by(func.count(WikipediaLink.id).desc())
        .options(
            selectinload(Language.wikidata_entity)
            .selectinload(WikidataEntity.parent_relations)
            .selectinload(WikidataRelation.parent_entity)
        )
    )

    # Apply search filter if provided
    if search:
        query = Language.search_by_label(query, search)

    # Apply offset and limit
    query = query.offset(offset).limit(limit)

    results = db.execute(query).all()

    return [
        LanguageResponse(
            wikidata_id=lang.wikidata_id,
            name=lang.name,
            description=lang.description,
            iso_639_1=lang.iso_639_1,
            iso_639_2=lang.iso_639_2,
            iso_639_3=lang.iso_639_3,
            sources_count=count,
        )
        for lang, count in results
    ]


@router.get("/countries", response_model=List[CountryResponse])
async def get_countries(
    limit: int = Query(
        default=100,
        le=1000,
        description="Maximum number of countries to return",
    ),
    offset: int = Query(default=0, ge=0, description="Number of countries to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search countries by name/label using fuzzy matching",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve countries that have politicians with citizenship.

    Returns a list of countries with their metadata and the count of
    politicians who have citizenship in each country.
    """
    # Direct query with grouping - no subquery needed
    query = (
        select(
            Country,
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
        .group_by(Country.wikidata_id)
        .order_by(func.count(Property.id).desc())
        .options(
            selectinload(Country.wikidata_entity)
            .selectinload(WikidataEntity.parent_relations)
            .selectinload(WikidataRelation.parent_entity)
        )
    )

    # Apply search filter if provided
    if search:
        query = Country.search_by_label(query, search)

    # Apply offset and limit
    query = query.offset(offset).limit(limit)

    results = db.execute(query).all()

    return [
        CountryResponse(
            wikidata_id=country.wikidata_id,
            name=country.name,
            description=country.description,
            iso_code=country.iso_code,
            citizenships_count=count,
        )
        for country, count in results
    ]


get_positions = router.get("/positions", response_model=List[PositionResponse])(
    create_entity_endpoint(
        model_class=Position,
        response_mapper=lambda position: PositionResponse(
            wikidata_id=position.wikidata_id,
            name=position.name,
            description=position.description,
        ),
        entity_name="positions",
    )
)

get_locations = router.get("/locations", response_model=List[LocationResponse])(
    create_entity_endpoint(
        model_class=Location,
        response_mapper=lambda location: LocationResponse(
            wikidata_id=location.wikidata_id,
            name=location.name,
            description=location.description,
        ),
        entity_name="locations",
    )
)

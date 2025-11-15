"""API endpoints for entities like languages and countries."""

from typing import List, Optional, Type, Callable
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_

from ..database import get_engine
from ..models import (
    Language,
    Country,
    Position,
    Location,
    WikidataEntity,
    WikipediaLink,
    Property,
)
from ..models.base import PropertyType
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
        current_user: User = Depends(get_current_user),
    ):
        f"""
        Retrieve {entity_name} with optional search filtering.

        Returns a list of {entity_name} with their metadata.
        Supports fuzzy text search on labels.
        """
        with Session(get_engine()) as db:
            # Build base query filtering out soft-deleted entities
            query = (
                select(model_class)
                .join(
                    WikidataEntity,
                    model_class.wikidata_id == WikidataEntity.wikidata_id,
                )
                .where(WikidataEntity.deleted_at.is_(None))
            )

            # Add eager loading for wikidata_entity with parent_relations
            query = query.options(
                selectinload(model_class.wikidata_entity).selectinload(
                    WikidataEntity.parent_relations
                )
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
async def get_languages(current_user=Depends(get_current_user)):
    """
    Retrieve all languages with source counts.

    Returns a list of all languages with their metadata and the count of
    sources (currently Wikipedia links) using each language's ISO code.
    """
    with Session(get_engine()) as db:
        # Subquery to count sources per language ISO code
        # Currently only Wikipedia links, but may include other source types in the future
        sources_count_subquery = (
            select(
                WikipediaLink.iso_code,
                func.count(WikipediaLink.id).label("link_count"),
            )
            .group_by(WikipediaLink.iso_code)
            .subquery()
        )

        # Query languages with their source counts
        query = (
            select(
                Language,
                func.coalesce(sources_count_subquery.c.link_count, 0).label(
                    "sources_count"
                ),
            )
            .join(
                WikidataEntity,
                Language.wikidata_id == WikidataEntity.wikidata_id,
            )
            .join(
                sources_count_subquery,
                or_(
                    Language.iso1_code == sources_count_subquery.c.iso_code,
                    Language.iso3_code == sources_count_subquery.c.iso_code,
                ),
            )
            .where(WikidataEntity.deleted_at.is_(None))
            .order_by(sources_count_subquery.c.link_count.desc())
        )

        results = db.execute(query).all()

        return [
            LanguageResponse(
                wikidata_id=lang.wikidata_id,
                name=lang.name,
                description=lang.description,
                iso1_code=lang.iso1_code,
                iso3_code=lang.iso3_code,
                sources_count=count,
            )
            for lang, count in results
        ]


@router.get("/countries", response_model=List[CountryResponse])
async def get_countries(current_user=Depends(get_current_user)):
    """
    Retrieve all countries with citizenship counts.

    Returns a list of all countries with their metadata and the count of
    politicians who have citizenship in each country.
    """
    with Session(get_engine()) as db:
        # Subquery to count citizenship properties per country
        citizenship_count_subquery = (
            select(
                Property.entity_id,
                func.count(Property.id).label("citizenship_count"),
            )
            .where(Property.type == PropertyType.CITIZENSHIP)
            .group_by(Property.entity_id)
            .subquery()
        )

        # Query countries with their citizenship counts
        query = (
            select(
                Country,
                func.coalesce(citizenship_count_subquery.c.citizenship_count, 0).label(
                    "citizenships_count"
                ),
            )
            .join(
                WikidataEntity,
                Country.wikidata_id == WikidataEntity.wikidata_id,
            )
            .join(
                citizenship_count_subquery,
                Country.wikidata_id == citizenship_count_subquery.c.entity_id,
            )
            .where(WikidataEntity.deleted_at.is_(None))
            .order_by(citizenship_count_subquery.c.citizenship_count.desc())
        )

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

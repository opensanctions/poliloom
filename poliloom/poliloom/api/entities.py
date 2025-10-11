"""API endpoints for entities like languages and countries."""

from typing import List, Optional, Type, Callable
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_engine
from ..models import Language, Country, Position, Location, WikidataEntity
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
            le=100,
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
                query = model_class.search_by_label(query, search, session=db)

            # Apply offset and limit
            query = query.offset(offset).limit(limit)

            # Execute query
            entities = db.execute(query).scalars().all()

            return [response_mapper(entity) for entity in entities]

    return endpoint


# Register endpoints using the factory
get_languages = router.get("/languages", response_model=List[LanguageResponse])(
    create_entity_endpoint(
        model_class=Language,
        response_mapper=lambda lang: LanguageResponse(
            wikidata_id=lang.wikidata_id,
            name=lang.name,
            description=lang.description,
            iso1_code=lang.iso1_code,
            iso3_code=lang.iso3_code,
        ),
        entity_name="languages",
    )
)

get_countries = router.get("/countries", response_model=List[CountryResponse])(
    create_entity_endpoint(
        model_class=Country,
        response_mapper=lambda country: CountryResponse(
            wikidata_id=country.wikidata_id,
            name=country.name,
            description=country.description,
            iso_code=country.iso_code,
        ),
        entity_name="countries",
    )
)

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

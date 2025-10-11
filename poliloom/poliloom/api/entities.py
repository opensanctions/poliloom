"""API endpoints for entities like languages and countries."""

from typing import List, Optional
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


@router.get("/languages", response_model=List[LanguageResponse])
async def get_languages(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all languages with their metadata.

    Returns a list of all languages with their Wikidata IDs, names, and ISO codes.
    """
    with Session(get_engine()) as db:
        stmt = select(Language).options(selectinload(Language.wikidata_entity))

        languages = db.execute(stmt).scalars().all()

        return [
            LanguageResponse(
                wikidata_id=lang.wikidata_id,
                name=lang.name,
                iso1_code=lang.iso1_code,
                iso3_code=lang.iso3_code,
            )
            for lang in languages
        ]


@router.get("/countries", response_model=List[CountryResponse])
async def get_countries(
    limit: int = Query(
        default=100, le=100, description="Maximum number of countries to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of countries to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search countries by name/label using fuzzy matching",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve countries with optional search filtering.

    Returns a list of countries with their Wikidata IDs, names, and ISO codes.
    Supports fuzzy text search on country labels.
    """
    with Session(get_engine()) as db:
        # Build base query filtering out soft-deleted entities
        query = (
            select(Country)
            .join(WikidataEntity, Country.wikidata_id == WikidataEntity.wikidata_id)
            .where(WikidataEntity.deleted_at.is_(None))
            .options(selectinload(Country.wikidata_entity))
        )

        # Apply search filter if provided
        if search:
            query = Country.search_by_label(query, search)

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        countries = db.execute(query).scalars().all()

        return [
            CountryResponse(
                wikidata_id=country.wikidata_id,
                name=country.name,
                iso_code=country.iso_code,
            )
            for country in countries
        ]


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    limit: int = Query(
        default=100, le=100, description="Maximum number of positions to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of positions to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search positions by name/label using fuzzy matching",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve positions with optional search filtering.

    Returns a list of positions with their Wikidata IDs, names, and descriptions.
    Supports fuzzy text search on position labels.
    """
    with Session(get_engine()) as db:
        # Build base query filtering out soft-deleted entities
        query = (
            select(Position)
            .join(WikidataEntity, Position.wikidata_id == WikidataEntity.wikidata_id)
            .where(WikidataEntity.deleted_at.is_(None))
            .options(
                selectinload(Position.wikidata_entity).selectinload(
                    WikidataEntity.parent_relations
                )
            )
        )

        # Apply search filter if provided
        if search:
            query = Position.search_by_label(query, search)

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        positions = db.execute(query).scalars().all()

        return [
            PositionResponse(
                wikidata_id=position.wikidata_id,
                name=position.name,
                description=position.description,
            )
            for position in positions
        ]


@router.get("/locations", response_model=List[LocationResponse])
async def get_locations(
    limit: int = Query(
        default=100, le=100, description="Maximum number of locations to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of locations to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search locations by name/label using fuzzy matching",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve locations with optional search filtering.

    Returns a list of locations with their Wikidata IDs, names, and descriptions.
    Supports fuzzy text search on location labels.
    """
    with Session(get_engine()) as db:
        # Build base query filtering out soft-deleted entities
        query = (
            select(Location)
            .join(WikidataEntity, Location.wikidata_id == WikidataEntity.wikidata_id)
            .where(WikidataEntity.deleted_at.is_(None))
            .options(
                selectinload(Location.wikidata_entity).selectinload(
                    WikidataEntity.parent_relations
                )
            )
        )

        # Apply search filter if provided
        if search:
            query = Location.search_by_label(query, search)

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        locations = db.execute(query).scalars().all()

        return [
            LocationResponse(
                wikidata_id=location.wikidata_id,
                name=location.name,
                description=location.description,
            )
            for location in locations
        ]

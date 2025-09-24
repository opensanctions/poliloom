"""API endpoints for entities like languages and countries."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_engine
from ..models import Language, Country
from .schemas import LanguageResponse, CountryResponse
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
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all countries with their metadata.

    Returns a list of all countries with their Wikidata IDs, names, and ISO codes.
    """
    with Session(get_engine()) as db:
        stmt = select(Country).options(selectinload(Country.wikidata_entity))

        countries = db.execute(stmt).scalars().all()

        return [
            CountryResponse(
                wikidata_id=country.wikidata_id,
                name=country.name,
                iso_code=country.iso_code,
            )
            for country in countries
        ]

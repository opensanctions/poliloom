"""User preferences API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, delete
from pydantic import BaseModel

from ..database import get_engine
from ..models import (
    Preference,
    PreferenceType,
    Country,
    Language,
)
from .auth import get_current_user, User

router = APIRouter()


class PreferenceResponse(BaseModel):
    """Schema for preference response."""

    wikidata_id: str
    name: str
    preference_type: str


class PreferenceRequest(BaseModel):
    """Schema for preference request."""

    wikidata_ids: List[str]


@router.get("", response_model=List[PreferenceResponse])
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
):
    """Get all user preferences as a flat list."""
    with Session(get_engine()) as db:
        query = (
            select(Preference)
            .options(selectinload(Preference.entity))
            .where(Preference.user_id == str(current_user.user_id))
        )

        preferences = db.execute(query).scalars().all()

        result = []
        for pref in preferences:
            if pref.entity:
                result.append(
                    PreferenceResponse(
                        wikidata_id=pref.entity_id,
                        name=pref.entity.name or pref.entity_id,
                        preference_type=pref.preference_type.value,
                    )
                )

        return result


@router.post("/{preference_type}")
async def set_user_preferences(
    request: PreferenceRequest,
    preference_type: PreferenceType = Path(
        ..., description="Type of preferences to set"
    ),
    current_user: User = Depends(get_current_user),
):
    """Replace all user preferences for a specific type with the provided list."""
    with Session(get_engine()) as db:
        user_id = str(current_user.user_id)

        # Validate entity QIDs exist in the appropriate table
        if request.wikidata_ids:
            if preference_type == PreferenceType.COUNTRY:
                # Validate country QIDs exist in countries table
                existing_entities = (
                    db.execute(
                        select(Country.wikidata_id).where(
                            Country.wikidata_id.in_(request.wikidata_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                entity_type = "countries"
            else:  # PreferenceType.LANGUAGE
                # Validate language QIDs exist in languages table
                existing_entities = (
                    db.execute(
                        select(Language.wikidata_id).where(
                            Language.wikidata_id.in_(request.wikidata_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                entity_type = "languages"

            existing_entity_set = set(existing_entities)
            missing_entities = set(request.wikidata_ids) - existing_entity_set

            if missing_entities:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown {entity_type} QIDs: {sorted(missing_entities)}",
                )

        # Remove all existing preferences of this type for the user
        delete_stmt = delete(Preference).where(
            Preference.user_id == user_id,
            Preference.preference_type == preference_type,
        )
        db.execute(delete_stmt)

        # Add new preferences
        if request.wikidata_ids:
            new_preferences = []
            for qid in request.wikidata_ids:
                new_preferences.append(
                    Preference(
                        user_id=user_id,
                        preference_type=preference_type,
                        entity_id=qid,
                    )
                )
            db.add_all(new_preferences)

        try:
            db.commit()
            return {
                "success": True,
                "message": f"Updated {len(request.wikidata_ids)} preferences",
            }

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}",
            )

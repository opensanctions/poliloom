"""API endpoint for the authenticated user's settings and filter preferences."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import PreferenceType, UserFilterPreference, UserSettings
from ..models.wikidata import WikidataEntity
from .auth import User, get_current_user
from .schemas import (
    UserFilterEntity,
    UserFiltersPatch,
    UserFiltersResponse,
    UserPatchRequest,
    UserResponse,
    UserSettingsPatch,
    UserSettingsResponse,
)


class UserFilters(BaseModel):
    """Resolved user filter QIDs, bucketed by type."""

    languages: list[str]
    countries: list[str]


def get_user_filters(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserFilters:
    """Resolve the authenticated user's stored filter preferences into QID lists."""
    rows = db.execute(
        select(
            UserFilterPreference.preference_type, UserFilterPreference.entity_id
        ).where(UserFilterPreference.user_id == str(user.user_id))
    ).all()
    return UserFilters(
        languages=[e for t, e in rows if t == PreferenceType.LANGUAGE],
        countries=[e for t, e in rows if t == PreferenceType.COUNTRY],
    )


router = APIRouter()


def _build_response(db: Session, settings: UserSettings) -> UserResponse:
    """Build the GET response shape from a loaded UserSettings row."""
    rows = db.execute(
        select(
            UserFilterPreference.preference_type,
            WikidataEntity.wikidata_id,
            WikidataEntity.name,
        )
        .join(
            WikidataEntity, WikidataEntity.wikidata_id == UserFilterPreference.entity_id
        )
        .where(
            UserFilterPreference.user_id == settings.user_id,
            WikidataEntity.deleted_at.is_(None),
        )
    ).all()

    languages = [
        UserFilterEntity(wikidata_id=qid, name=name)
        for t, qid, name in rows
        if t == PreferenceType.LANGUAGE
    ]
    countries = [
        UserFilterEntity(wikidata_id=qid, name=name)
        for t, qid, name in rows
        if t == PreferenceType.COUNTRY
    ]

    return UserResponse(
        settings=UserSettingsResponse.model_validate(settings),
        filters=UserFiltersResponse(language=languages, country=countries),
    )


@router.get("", response_model=Optional[UserResponse])
async def get_user(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's settings + filters, or null if no row exists."""
    user_id = str(current_user.user_id)
    settings = db.get(UserSettings, user_id)
    if settings is None:
        return None
    return _build_response(db, settings)


def _apply_filter_replacement(
    db: Session,
    user_id: str,
    preference_type: PreferenceType,
    entity_ids: list[str],
) -> None:
    """Validate and replace all rows of one preference_type for a user."""
    deduped = list(dict.fromkeys(entity_ids))  # dedupe, preserve order

    if deduped:
        existing = set(
            db.execute(
                select(WikidataEntity.wikidata_id).where(
                    WikidataEntity.wikidata_id.in_(deduped),
                    WikidataEntity.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        missing = [qid for qid in deduped if qid not in existing]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown wikidata entities: {', '.join(missing)}",
            )

    db.query(UserFilterPreference).filter(
        UserFilterPreference.user_id == user_id,
        UserFilterPreference.preference_type == preference_type,
    ).delete(synchronize_session=False)

    for qid in deduped:
        db.add(
            UserFilterPreference(
                user_id=user_id,
                preference_type=preference_type,
                entity_id=qid,
            )
        )


@router.patch("", response_model=UserResponse)
async def patch_user(
    body: UserPatchRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Apply a partial update to the user's settings and/or filters.

    Lazy-creates the user_settings row on first PATCH. For each filter type
    present in the body, replaces all existing rows of that type.
    """
    user_id = str(current_user.user_id)

    settings = db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.flush()

    if body.settings is not None:
        _apply_settings(settings, body.settings)

    if body.filters is not None:
        _apply_filters(db, user_id, body.filters)

    db.commit()
    db.refresh(settings)
    return _build_response(db, settings)


def _apply_settings(settings: UserSettings, patch: UserSettingsPatch) -> None:
    """Apply non-None fields from the settings patch onto the row."""
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)


def _apply_filters(db: Session, user_id: str, patch: UserFiltersPatch) -> None:
    """For each present filter type, replace its rows wholesale."""
    if patch.language is not None:
        _apply_filter_replacement(db, user_id, PreferenceType.LANGUAGE, patch.language)
    if patch.country is not None:
        _apply_filter_replacement(db, user_id, PreferenceType.COUNTRY, patch.country)

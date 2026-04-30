"""API endpoint for the authenticated user's settings and filter preferences."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import Language, PreferenceType, UserFilterPreference, UserSettings
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


def _parse_accept_language(header: str | None) -> list[str]:
    """Parse an Accept-Language header into a priority-ordered list of base codes.

    Returns lowercase ISO 639-1/2/3-style base tags ('en' from 'en-US'), deduped,
    ordered by descending q-value. Returns [] for empty/missing/wildcard input.
    """
    if not header:
        return []
    items: list[tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        tag, *params = part.split(";")
        q = 1.0
        for param in params:
            param = param.strip()
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    pass
        tag = tag.strip().lower()
        if not tag or tag == "*":
            continue
        base = tag.split("-")[0]
        items.append((base, q))
    items.sort(key=lambda x: -x[1])
    seen: set[str] = set()
    out: list[str] = []
    for base, _ in items:
        if base not in seen:
            seen.add(base)
            out.append(base)
    return out


def _detect_language_filters(db: Session, accept_language: str | None) -> list[str]:
    """Return Wikidata QIDs of languages matching the Accept-Language header.

    Preserves Accept-Language priority order. A code matches if it equals either
    `iso_639_1` or `iso_639_3` on a Language row.
    """
    codes = _parse_accept_language(accept_language)
    if not codes:
        return []
    rows = db.execute(
        select(Language.wikidata_id, Language.iso_639_1, Language.iso_639_3).where(
            or_(
                Language.iso_639_1.in_(codes),
                Language.iso_639_3.in_(codes),
            )
        )
    ).all()
    by_code: dict[str, str] = {}
    for qid, iso1, iso3 in rows:
        for code in (iso1, iso3):
            if code and code in codes and code not in by_code:
                by_code[code] = qid
    seen: set[str] = set()
    out: list[str] = []
    for code in codes:
        qid = by_code.get(code)
        if qid and qid not in seen:
            seen.add(qid)
            out.append(qid)
    return out


@router.get("", response_model=UserResponse)
async def get_user(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    accept_language: str | None = Header(default=None),
):
    """Return the authenticated user's settings + filters.

    On first read for a given user, lazy-creates the `user_settings` row and
    seeds language filters from the `Accept-Language` header (matching by
    ISO 639-1/3). Subsequent reads are pure.
    """
    user_id = str(current_user.user_id)
    settings = db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.flush()
        for qid in _detect_language_filters(db, accept_language):
            db.add(
                UserFilterPreference(
                    user_id=user_id,
                    preference_type=PreferenceType.LANGUAGE,
                    entity_id=qid,
                )
            )
        db.commit()
        db.refresh(settings)
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

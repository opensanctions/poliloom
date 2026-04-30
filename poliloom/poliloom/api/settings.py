"""API endpoint for the authenticated user's settings."""

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import UserSettings
from .auth import User, get_current_user
from .schemas import UserSettingsPatch, UserSettingsResponse


router = APIRouter()


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's settings, or schema defaults if no row exists."""
    settings = db.get(UserSettings, str(current_user.user_id))
    if settings is None:
        return UserSettingsResponse()
    return UserSettingsResponse.model_validate(settings)


@router.patch("", response_model=UserSettingsResponse)
async def patch_settings(
    body: UserSettingsPatch,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Apply a partial update to the user's settings, creating the row if needed."""
    user_id = str(current_user.user_id)
    patch = body.model_dump(exclude_unset=True)

    stmt = insert(UserSettings).values(user_id=user_id, **patch)
    if patch:
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={col: stmt.excluded[col] for col in patch},
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=["user_id"])
    db.execute(stmt)
    db.commit()

    settings = db.get(UserSettings, user_id)
    return UserSettingsResponse.model_validate(settings)

"""Sources API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..archiving import read_archived_content
from ..database import get_db_session
from ..models import Source
from .auth import User, get_current_user

router = APIRouter()


@router.get("/{source_id}.html")
async def get_source_html(
    source_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get source HTML content explicitly."""
    try:
        source_uuid = UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid source ID format",
        )

    source = db.get(Source, source_uuid)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )

    try:
        content = read_archived_content(source.path_root, "html")
        return HTMLResponse(content=content, media_type="text/html")
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

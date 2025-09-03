"""ArchivedPages API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, HTMLResponse
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_engine
from ..models import ArchivedPage
from .. import archive
from .auth import get_current_user, User

router = APIRouter()


@router.get("/{archived_page_id}.html")
async def get_archived_page_html(
    archived_page_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get archived page HTML content explicitly."""
    # Parse UUID
    try:
        page_id = UUID(archived_page_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid archived page ID format",
        )

    # Get archived page from database
    with Session(get_engine()) as db:
        archived_page = db.get(ArchivedPage, page_id)
        if not archived_page:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Archived page not found"
            )

        try:
            content = archive.read_archived_content(archived_page.path_root, "html")
            return HTMLResponse(content=content, media_type="text/html")
        except FileNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{archived_page_id}.md")
async def get_archived_page_markdown(
    archived_page_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get archived page markdown content explicitly."""
    # Parse UUID
    try:
        page_id = UUID(archived_page_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid archived page ID format",
        )

    # Get archived page from database
    with Session(get_engine()) as db:
        archived_page = db.get(ArchivedPage, page_id)
        if not archived_page:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Archived page not found"
            )

        try:
            content = archive.read_archived_content(archived_page.path_root, "md")
            return PlainTextResponse(content=content, media_type="text/markdown")
        except FileNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

"""ArchivedPages API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from uuid import UUID

from ..database import get_db_session
from ..models import (
    ArchivedPage,
    Politician,
    PoliticianArchivedPage,
    Property,
    PropertyReference,
)
from ..archiving import read_archived_content
from .auth import get_current_user, User
from .schemas import (
    PatchPropertiesResponse,
    PoliticianResponse,
    SourcePatchPropertiesRequest,
)
from .politicians import build_politician_response, process_property_actions

router = APIRouter()


# .html route must be registered before the UUID-typed routes to avoid
# FastAPI matching "{uuid}.html" against the /{archived_page_id} UUID param.
@router.get("/{archived_page_id}.html")
async def get_archived_page_html(
    archived_page_id: str,
    db: Session = Depends(get_db_session),
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
    archived_page = db.get(ArchivedPage, page_id)
    if not archived_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Archived page not found"
        )

    try:
        content = read_archived_content(archived_page.path_root, "html")
        return HTMLResponse(content=content, media_type="text/html")
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{archived_page_id}", response_model=List[PoliticianResponse])
async def get_source_page(
    archived_page_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get politicians linked to this archived page with their properties referencing it."""
    archived_page = db.get(ArchivedPage, archived_page_id)
    if not archived_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived page not found",
        )

    # Query politicians linked to this archived page via the junction table
    query = (
        select(Politician)
        .join(
            PoliticianArchivedPage,
            PoliticianArchivedPage.politician_id == Politician.id,
        )
        .where(PoliticianArchivedPage.archived_page_id == archived_page_id)
        .options(
            selectinload(
                Politician.properties.and_(
                    Property.deleted_at.is_(None),
                    Property.id.in_(
                        select(Property.id)
                        .join(PropertyReference)
                        .where(PropertyReference.archived_page_id == archived_page_id)
                    ),
                )
            ).options(
                selectinload(Property.entity),
                selectinload(
                    Property.property_references.and_(
                        PropertyReference.archived_page_id == archived_page_id
                    )
                ).selectinload(PropertyReference.archived_page),
            ),
        )
    )

    politicians = db.execute(query).scalars().all()

    return [build_politician_response(politician) for politician in politicians]


@router.patch("/{archived_page_id}/properties", response_model=PatchPropertiesResponse)
async def patch_source_properties(
    archived_page_id: UUID,
    request: SourcePatchPropertiesRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Accept, reject, or create properties from a source page context.

    Items are keyed by politician QID.
    """
    archived_page = db.get(ArchivedPage, archived_page_id)
    if not archived_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived page not found",
        )

    return await process_property_actions(request.items, db, current_user)

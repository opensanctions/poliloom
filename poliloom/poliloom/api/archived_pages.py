"""ArchivedPages API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from uuid import UUID

from ..database import get_db_session
from ..models import ArchivedPage, Politician, Property, PropertyReference
from .. import archive
from .auth import get_current_user, User
from .schemas import (
    ArchivedPageResponse,
    PatchPropertiesResponse,
    PoliticianResponse,
    SourcePageResponse,
    SourcePatchPropertiesRequest,
)
from .politicians import build_property_responses, process_property_actions

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
        content = archive.read_archived_content(archived_page.path_root, "html")
        return HTMLResponse(content=content, media_type="text/html")
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{archived_page_id}", response_model=SourcePageResponse)
async def get_source_page(
    archived_page_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get archived page metadata with all politicians and their properties referencing this page."""
    archived_page = db.get(ArchivedPage, archived_page_id)
    if not archived_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived page not found",
        )

    # Query politicians that have properties referencing this archived page
    query = (
        select(Politician)
        .join(Property, Property.politician_id == Politician.id)
        .join(PropertyReference, PropertyReference.property_id == Property.id)
        .where(
            PropertyReference.archived_page_id == archived_page_id,
            Property.deleted_at.is_(None),
        )
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
        .distinct()
    )

    politicians = db.execute(query).scalars().all()

    return SourcePageResponse(
        archived_page=ArchivedPageResponse(
            id=archived_page.id,
            url=archived_page.url,
            content_hash=archived_page.content_hash,
            fetch_timestamp=archived_page.fetch_timestamp,
        ),
        politicians=[
            PoliticianResponse(
                id=politician.id,
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                properties=build_property_responses(politician.properties),
            )
            for politician in politicians
        ],
    )


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

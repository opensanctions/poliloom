"""Sources API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from uuid import UUID

from ..database import get_db_session
from ..models import (
    Source,
    Politician,
    PoliticianSource,
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
# FastAPI matching "{uuid}.html" against the /{source_id} UUID param.
@router.get("/{source_id}.html")
async def get_source_html(
    source_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get source HTML content explicitly."""
    # Parse UUID
    try:
        page_id = UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid source ID format",
        )

    # Get source from database
    source = db.get(Source, page_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )

    try:
        content = read_archived_content(source.path_root, "html")
        return HTMLResponse(content=content, media_type="text/html")
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{source_id}", response_model=List[PoliticianResponse])
async def get_source_page(
    source_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get politicians linked to this source with their properties referencing it."""
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Query politicians linked to this source via the junction table
    query = (
        select(Politician)
        .join(
            PoliticianSource,
            PoliticianSource.politician_id == Politician.id,
        )
        .where(PoliticianSource.source_id == source_id)
        .options(
            selectinload(
                Politician.properties.and_(
                    Property.deleted_at.is_(None),
                    Property.id.in_(
                        select(Property.id)
                        .join(PropertyReference)
                        .where(PropertyReference.source_id == source_id)
                    ),
                )
            ).options(
                selectinload(Property.entity),
                selectinload(
                    Property.property_references.and_(
                        PropertyReference.source_id == source_id
                    )
                ).selectinload(PropertyReference.source),
            ),
        )
    )

    politicians = db.execute(query).scalars().all()

    return [build_politician_response(politician) for politician in politicians]


@router.patch("/{source_id}/properties", response_model=PatchPropertiesResponse)
async def patch_source_properties(
    source_id: UUID,
    request: SourcePatchPropertiesRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Accept, reject, or create properties from a source page context.

    Items are keyed by politician QID.
    """
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    return await process_property_actions(request.items, db, current_user)

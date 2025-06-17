"""Politicians API endpoints."""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_db
from ..models import Politician, Property, HoldsPosition
from .schemas import (
    UnconfirmedPoliticianResponse, 
    UnconfirmedPropertyResponse, 
    UnconfirmedPositionResponse,
    ConfirmationRequest,
    ConfirmationResponse
)
from .auth import get_current_user, User

router = APIRouter()


@router.get("/unconfirmed", response_model=List[UnconfirmedPoliticianResponse])
async def get_unconfirmed_politicians(
    limit: int = Query(default=50, le=100, description="Maximum number of politicians to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve politicians that have unconfirmed (is_extracted=True) properties or positions.
    
    Returns a list of politicians with their unconfirmed data for review and confirmation.
    """
    # Query for politicians that have either unconfirmed properties or positions
    query = (
        select(Politician)
        .options(
            selectinload(Politician.properties),
            selectinload(Politician.positions_held).selectinload(HoldsPosition.position),
            selectinload(Politician.positions_held).selectinload(HoldsPosition.sources)
        )
        .where(
            (Politician.properties.any(Property.is_extracted == True)) |
            (Politician.positions_held.any(HoldsPosition.is_extracted == True))
        )
        .offset(offset)
        .limit(limit)
    )
    
    politicians = db.execute(query).scalars().all()
    
    result = []
    for politician in politicians:
        # Filter unconfirmed properties
        unconfirmed_properties = [
            prop for prop in politician.properties 
            if prop.is_extracted and prop.confirmed_at is None
        ]
        
        # Filter unconfirmed positions
        unconfirmed_positions = [
            pos for pos in politician.positions_held 
            if pos.is_extracted and pos.confirmed_at is None
        ]
        
        # Only include politicians that actually have unconfirmed data
        if unconfirmed_properties or unconfirmed_positions:
            politician_response = UnconfirmedPoliticianResponse(
                id=politician.id,
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                unconfirmed_properties=[
                    UnconfirmedPropertyResponse(
                        id=prop.id,
                        type=prop.type,
                        value=prop.value,
                        source_urls=[source.url for source in prop.sources]
                    )
                    for prop in unconfirmed_properties
                ],
                unconfirmed_positions=[
                    UnconfirmedPositionResponse(
                        id=pos.id,
                        position_name=pos.position.name,
                        start_date=pos.start_date,
                        end_date=pos.end_date,
                        source_urls=[source.url for source in pos.sources]
                    )
                    for pos in unconfirmed_positions
                ]
            )
            result.append(politician_response)
    
    return result


@router.post("/{politician_id}/confirm", response_model=ConfirmationResponse)
async def confirm_politician_data(
    politician_id: str,
    confirmation: ConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm or discard extracted properties and positions for a politician.
    
    This endpoint allows authenticated users to review and confirm extracted data,
    marking it as verified or discarding incorrect extractions.
    """
    # Verify politician exists
    politician = db.get(Politician, politician_id)
    if not politician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Politician not found"
        )
    
    confirmed_count = 0
    discarded_count = 0
    errors = []
    
    # Process confirmed properties
    for prop_id in confirmation.confirmed_properties:
        prop = db.get(Property, prop_id)
        if not prop:
            errors.append(f"Property {prop_id} not found")
            continue
        if prop.politician_id != politician_id:
            errors.append(f"Property {prop_id} does not belong to politician {politician_id}")
            continue
        
        prop.is_extracted = False
        prop.confirmed_by = current_user.username
        prop.confirmed_at = datetime.utcnow()
        confirmed_count += 1
    
    # Process discarded properties
    for prop_id in confirmation.discarded_properties:
        prop = db.get(Property, prop_id)
        if not prop:
            errors.append(f"Property {prop_id} not found")
            continue
        if prop.politician_id != politician_id:
            errors.append(f"Property {prop_id} does not belong to politician {politician_id}")
            continue
        
        # Mark as discarded by removing from database or setting a flag
        db.delete(prop)
        discarded_count += 1
    
    # Process confirmed positions
    for pos_id in confirmation.confirmed_positions:
        pos = db.get(HoldsPosition, pos_id)
        if not pos:
            errors.append(f"Position {pos_id} not found")
            continue
        if pos.politician_id != politician_id:
            errors.append(f"Position {pos_id} does not belong to politician {politician_id}")
            continue
        
        pos.is_extracted = False
        pos.confirmed_by = current_user.username
        pos.confirmed_at = datetime.utcnow()
        confirmed_count += 1
    
    # Process discarded positions
    for pos_id in confirmation.discarded_positions:
        pos = db.get(HoldsPosition, pos_id)
        if not pos:
            errors.append(f"Position {pos_id} not found")
            continue
        if pos.politician_id != politician_id:
            errors.append(f"Position {pos_id} does not belong to politician {politician_id}")
            continue
        
        # Mark as discarded by removing from database
        db.delete(pos)
        discarded_count += 1
    
    try:
        db.commit()
        return ConfirmationResponse(
            success=True,
            message=f"Successfully processed {confirmed_count} confirmations and {discarded_count} discards",
            confirmed_count=confirmed_count,
            discarded_count=discarded_count,
            errors=errors
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
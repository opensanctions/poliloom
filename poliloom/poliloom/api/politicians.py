"""Politicians API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_db
from ..models import Politician, Property, HoldsPosition
from .schemas import UnconfirmedPoliticianResponse, UnconfirmedPropertyResponse, UnconfirmedPositionResponse

router = APIRouter()


@router.get("/unconfirmed", response_model=List[UnconfirmedPoliticianResponse])
async def get_unconfirmed_politicians(
    limit: int = Query(default=50, le=100, description="Maximum number of politicians to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
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
            (Politician.properties.any(Property.is_extracted)) |
            (Politician.positions_held.any(HoldsPosition.is_extracted))
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
"""Pydantic schemas for API responses."""
from typing import List, Optional
from pydantic import BaseModel


class UnconfirmedPropertyResponse(BaseModel):
    """Schema for unconfirmed property data."""
    id: str
    type: str
    value: str
    source_urls: List[str]

    class Config:
        from_attributes = True


class UnconfirmedPositionResponse(BaseModel):
    """Schema for unconfirmed position data."""
    id: str
    position_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source_urls: List[str]

    class Config:
        from_attributes = True


class UnconfirmedPoliticianResponse(BaseModel):
    """Schema for politician with unconfirmed data."""
    id: str
    name: str
    wikidata_id: Optional[str] = None
    unconfirmed_properties: List[UnconfirmedPropertyResponse]
    unconfirmed_positions: List[UnconfirmedPositionResponse]

    class Config:
        from_attributes = True
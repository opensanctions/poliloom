"""Pydantic schemas for API responses."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class UnconfirmedPropertyResponse(BaseModel):
    """Schema for unconfirmed property data."""

    id: str
    type: str
    value: str
    source_urls: List[str]

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedPositionResponse(BaseModel):
    """Schema for unconfirmed position data."""

    id: str
    position_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source_urls: List[str]

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedBirthplaceResponse(BaseModel):
    """Schema for unconfirmed birthplace data."""

    id: str
    location_name: str
    location_wikidata_id: Optional[str] = None
    source_urls: List[str]

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedPoliticianResponse(BaseModel):
    """Schema for politician with unconfirmed data."""

    id: str
    name: str
    wikidata_id: Optional[str] = None
    unconfirmed_properties: List[UnconfirmedPropertyResponse]
    unconfirmed_positions: List[UnconfirmedPositionResponse]
    unconfirmed_birthplaces: List[UnconfirmedBirthplaceResponse]

    model_config = ConfigDict(from_attributes=True)


class ConfirmationRequest(BaseModel):
    """Schema for confirmation request body."""

    confirmed_properties: List[str] = []
    discarded_properties: List[str] = []
    confirmed_positions: List[str] = []
    discarded_positions: List[str] = []
    confirmed_birthplaces: List[str] = []
    discarded_birthplaces: List[str] = []


class ConfirmationResponse(BaseModel):
    """Schema for confirmation response."""

    success: bool
    message: str
    confirmed_count: int
    discarded_count: int
    errors: List[str] = []

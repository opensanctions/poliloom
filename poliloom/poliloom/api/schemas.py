"""Pydantic schemas for API responses."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum


class EvaluationResultEnum(str, Enum):
    """Enum for evaluation results."""

    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class UnconfirmedPropertyResponse(BaseModel):
    """Schema for unconfirmed property data."""

    id: str
    type: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedPositionResponse(BaseModel):
    """Schema for unconfirmed position data."""

    id: str
    position_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedBirthplaceResponse(BaseModel):
    """Schema for unconfirmed birthplace data."""

    id: str
    location_name: str
    location_wikidata_id: Optional[str] = None

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


class EvaluationItem(BaseModel):
    """Schema for individual evaluation item."""

    entity_type: str  # "property", "position", "birthplace"
    entity_id: str
    result: EvaluationResultEnum


class EvaluationRequest(BaseModel):
    """Schema for evaluation request body."""

    evaluations: List[EvaluationItem]


class EvaluationResponse(BaseModel):
    """Schema for evaluation response."""

    success: bool
    message: str
    processed_count: int
    errors: List[str] = []

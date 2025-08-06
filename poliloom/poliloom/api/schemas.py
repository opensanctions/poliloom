"""Pydantic schemas for API responses."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ArchivedPageResponse(BaseModel):
    """Schema for archived page data."""

    id: str
    url: str
    content_hash: str
    fetch_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedPropertyResponse(BaseModel):
    """Schema for unconfirmed property data."""

    id: str
    type: str
    value: str
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedPositionResponse(BaseModel):
    """Schema for unconfirmed position data."""

    id: str
    position_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UnconfirmedBirthplaceResponse(BaseModel):
    """Schema for unconfirmed birthplace data."""

    id: str
    location_name: str
    location_wikidata_id: Optional[str] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None

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


class PropertyEvaluationItem(BaseModel):
    """Schema for property evaluation item."""

    id: str
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "is_confirmed": True,
            }
        }
    )


class PositionEvaluationItem(BaseModel):
    """Schema for position evaluation item."""

    id: str
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "87654321-4321-4321-4321-210987654321",
                "is_confirmed": False,
            }
        }
    )


class BirthplaceEvaluationItem(BaseModel):
    """Schema for birthplace evaluation item."""

    id: str
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "11111111-2222-3333-4444-555555555555",
                "is_confirmed": True,
            }
        }
    )


class EvaluationRequest(BaseModel):
    """Schema for evaluation request body."""

    property_evaluations: List[PropertyEvaluationItem] = []
    position_evaluations: List[PositionEvaluationItem] = []
    birthplace_evaluations: List[BirthplaceEvaluationItem] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "property_evaluations": [
                    {
                        "id": "12345678-1234-1234-1234-123456789012",
                        "is_confirmed": True,
                    },
                    {
                        "id": "22222222-1234-1234-1234-123456789012",
                        "is_confirmed": False,
                    },
                ],
                "position_evaluations": [
                    {"id": "87654321-4321-4321-4321-210987654321", "is_confirmed": True}
                ],
                "birthplace_evaluations": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "is_confirmed": False,
                    }
                ],
            }
        }
    )


class EvaluationResponse(BaseModel):
    """Schema for evaluation response."""

    success: bool
    message: str
    property_count: int
    position_count: int
    birthplace_count: int
    errors: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully processed 4 evaluations",
                "property_count": 2,
                "position_count": 1,
                "birthplace_count": 1,
                "errors": [],
            }
        }
    )

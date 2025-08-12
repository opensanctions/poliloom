"""Pydantic schemas for API responses."""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime


class UUIDBaseModel(BaseModel):
    """Base model with automatic UUID to string serialization."""

    @field_serializer("id", when_used="always", check_fields=False)
    def serialize_uuid(self, value: UUID) -> str:
        return str(value) if value else None

    model_config = ConfigDict(from_attributes=True)


class ArchivedPageResponse(UUIDBaseModel):
    """Schema for archived page data."""

    id: UUID
    url: str
    content_hash: str
    fetch_timestamp: datetime


class ExtractedPropertyResponse(UUIDBaseModel):
    """Schema for extracted property data."""

    id: UUID
    type: str
    value: str
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None


class ExtractedPositionResponse(UUIDBaseModel):
    """Schema for extracted position data."""

    id: UUID
    position_name: str
    wikidata_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None


class ExtractedBirthplaceResponse(UUIDBaseModel):
    """Schema for extracted birthplace data."""

    id: UUID
    location_name: str
    wikidata_id: Optional[str] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None


class WikidataPropertyResponse(UUIDBaseModel):
    """Schema for Wikidata property data."""

    id: UUID
    type: str
    value: str
    value_precision: Optional[int] = None


class WikidataPositionResponse(UUIDBaseModel):
    """Schema for Wikidata position data."""

    id: UUID
    position_name: str
    wikidata_id: Optional[str] = None
    start_date: Optional[str] = None
    start_date_precision: Optional[int] = None
    end_date: Optional[str] = None
    end_date_precision: Optional[int] = None


class WikidataBirthplaceResponse(UUIDBaseModel):
    """Schema for Wikidata birthplace data."""

    id: UUID
    location_name: str
    wikidata_id: Optional[str] = None


class PoliticianResponse(UUIDBaseModel):
    """Schema for politician with extracted and Wikidata data."""

    id: UUID
    name: str
    wikidata_id: Optional[str] = None
    wikidata_properties: List[WikidataPropertyResponse]
    wikidata_positions: List[WikidataPositionResponse]
    wikidata_birthplaces: List[WikidataBirthplaceResponse]
    extracted_properties: List[ExtractedPropertyResponse]
    extracted_positions: List[ExtractedPositionResponse]
    extracted_birthplaces: List[ExtractedBirthplaceResponse]


class PropertyEvaluationItem(UUIDBaseModel):
    """Schema for property evaluation item."""

    id: UUID
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "is_confirmed": True,
            }
        }
    )


class PositionEvaluationItem(UUIDBaseModel):
    """Schema for position evaluation item."""

    id: UUID
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "87654321-4321-4321-4321-210987654321",
                "is_confirmed": False,
            }
        }
    )


class BirthplaceEvaluationItem(UUIDBaseModel):
    """Schema for birthplace evaluation item."""

    id: UUID
    is_confirmed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "11111111-2222-3333-4444-555555555555",
                "is_confirmed": True,
            }
        }
    )


class EvaluationRequest(UUIDBaseModel):
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


class EvaluationResponse(UUIDBaseModel):
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

"""Pydantic schemas for API responses."""

from typing import List, Optional, Dict, Any
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


class PropertyStatementResponse(UUIDBaseModel):
    """Schema for property statements (birth_date, death_date)."""

    id: UUID
    value: str
    value_precision: Optional[int] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None
    statement_id: Optional[str] = None


class PositionStatementResponse(UUIDBaseModel):
    """Schema for position statements (holds_position relationships)."""

    id: UUID
    start_date: Optional[str] = None
    start_date_precision: Optional[int] = None
    end_date: Optional[str] = None
    end_date_precision: Optional[int] = None
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None
    statement_id: Optional[str] = None
    qualifiers: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None


class BirthplaceStatementResponse(UUIDBaseModel):
    """Schema for birthplace statements (born_at relationships)."""

    id: UUID
    proof_line: Optional[str] = None
    archived_page: Optional[ArchivedPageResponse] = None
    statement_id: Optional[str] = None
    qualifiers: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None


class PropertyResponse(UUIDBaseModel):
    """Schema for property with grouped statements."""

    type: str
    statements: List[PropertyStatementResponse]


class PositionResponse(UUIDBaseModel):
    """Schema for position with grouped statements."""

    qid: str
    name: str
    statements: List[PositionStatementResponse]


class BirthplaceResponse(UUIDBaseModel):
    """Schema for birthplace with grouped statements."""

    qid: str
    name: str
    statements: List[BirthplaceStatementResponse]


class PoliticianResponse(UUIDBaseModel):
    """Schema for politician with grouped statements."""

    id: UUID
    name: str
    wikidata_id: Optional[str] = None
    properties: List[PropertyResponse]
    positions: List[PositionResponse]
    birthplaces: List[BirthplaceResponse]


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

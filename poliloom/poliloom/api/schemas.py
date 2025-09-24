"""Pydantic schemas for API responses."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime
from ..models import PropertyType


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


class PropertyResponse(UUIDBaseModel):
    """Unified property response."""

    id: UUID
    type: PropertyType
    value: Optional[str] = None
    value_precision: Optional[int] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None  # Add for frontend convenience
    proof_line: Optional[str] = None
    statement_id: Optional[str] = None
    qualifiers: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None
    archived_page: Optional[ArchivedPageResponse] = None

    @field_serializer("type")
    def serialize_property_type(self, value: PropertyType) -> str:
        """Return enum name instead of value for better API readability."""
        return value.name if value else None


class PoliticianResponse(UUIDBaseModel):
    """Simplified politician response."""

    id: UUID
    name: str
    wikidata_id: str
    properties: List[PropertyResponse]  # Single flat list


class EvaluationItem(UUIDBaseModel):
    """Single evaluation item."""

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


class EvaluationRequest(UUIDBaseModel):
    """Simplified evaluation request."""

    evaluations: List[EvaluationItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "evaluations": [
                    {
                        "id": "12345678-1234-1234-1234-123456789012",
                        "is_confirmed": True,
                    },
                    {
                        "id": "22222222-1234-1234-1234-123456789012",
                        "is_confirmed": False,
                    },
                ]
            }
        }
    )


class EvaluationResponse(UUIDBaseModel):
    """Schema for evaluation response."""

    success: bool
    message: str
    evaluation_count: int
    errors: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully processed 4 evaluations",
                "evaluation_count": 4,
                "errors": [],
            }
        }
    )

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


class PropertyReferenceResponse(UUIDBaseModel):
    """Schema for a property reference (evidence source)."""

    id: UUID
    archived_page: ArchivedPageResponse
    supporting_quotes: Optional[List[str]] = None


class PropertyResponse(UUIDBaseModel):
    """Unified property response."""

    id: UUID
    type: PropertyType
    value: Optional[str] = None
    value_precision: Optional[int] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None  # Add for frontend convenience
    statement_id: Optional[str] = None
    qualifiers: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None
    sources: List[PropertyReferenceResponse] = []

    @field_serializer("type")
    def serialize_property_type(self, value: PropertyType) -> str:
        """Return enum value (Wikidata P... identifier) instead of name."""
        return value.value if value else None


class PoliticianResponse(UUIDBaseModel):
    """Simplified politician response."""

    id: UUID
    name: str
    wikidata_id: Optional[str] = None
    properties: List[PropertyResponse]  # Single flat list


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment status for empty state UX."""

    has_enrichable_politicians: bool = True
    total_matching_filters: int = 0


class PoliticiansListResponse(BaseModel):
    """Response for politicians list endpoint with enrichment metadata."""

    politicians: List[PoliticianResponse]
    meta: EnrichmentMetadata


class EvaluationItem(UUIDBaseModel):
    """Single evaluation item."""

    id: UUID
    is_accepted: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "is_accepted": True,
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
                        "is_accepted": True,
                    },
                    {
                        "id": "22222222-1234-1234-1234-123456789012",
                        "is_accepted": False,
                    },
                ]
            }
        }
    )


class EvaluationObjectResponse(UUIDBaseModel):
    """Schema for a single evaluation object."""

    id: UUID
    user_id: str
    is_accepted: bool
    property_id: UUID
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "98765432-4321-4321-4321-210987654321",
                "user_id": "12345",
                "is_accepted": True,
                "property_id": "12345678-1234-1234-1234-123456789012",
                "created_at": "2025-10-12T10:30:00Z",
            }
        }
    )


class EvaluationResponse(UUIDBaseModel):
    """Schema for evaluation response."""

    success: bool
    message: str
    evaluations: List[EvaluationObjectResponse] = []
    errors: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully processed 4 evaluations",
                "evaluations": [
                    {
                        "id": "98765432-4321-4321-4321-210987654321",
                        "user_id": "12345",
                        "is_accepted": True,
                        "property_id": "12345678-1234-1234-1234-123456789012",
                        "created_at": "2025-10-12T10:30:00Z",
                    }
                ],
                "errors": [],
            }
        }
    )


class LanguageResponse(BaseModel):
    """Schema for language response."""

    wikidata_id: str
    name: str
    description: Optional[str] = None
    iso_639_1: Optional[str] = None
    iso_639_3: Optional[str] = None
    sources_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    """Schema for country response."""

    wikidata_id: str
    name: str
    description: Optional[str] = None
    citizenships_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PositionResponse(BaseModel):
    """Schema for position response."""

    wikidata_id: str
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LocationResponse(BaseModel):
    """Schema for location response."""

    wikidata_id: str
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

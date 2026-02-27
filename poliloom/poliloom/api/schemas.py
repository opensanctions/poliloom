"""Pydantic schemas for API responses."""

from typing import Annotated, List, Literal, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Discriminator, Tag, field_serializer
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


class SourcePageResponse(BaseModel):
    """Response for GET /archived-pages/{id} — source-centric view."""

    archived_page: ArchivedPageResponse
    politicians: List[PoliticianResponse]


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment status for empty state UX."""

    has_enrichable_politicians: bool = True
    total_matching_filters: int = 0


class NextPoliticianResponse(BaseModel):
    """Response for next politician endpoint - lightweight, returns only QID."""

    wikidata_id: Optional[str] = None
    meta: EnrichmentMetadata


class AcceptPropertyItem(BaseModel):
    action: Literal["accept"]
    id: UUID


class RejectPropertyItem(BaseModel):
    action: Literal["reject"]
    id: UUID


class CreatePropertyItem(BaseModel):
    action: Literal["create"]
    type: str
    value: Optional[str] = None
    value_precision: Optional[int] = None
    entity_id: Optional[str] = None
    qualifiers: Optional[Dict[str, Any]] = None


PropertyActionItem = Annotated[
    Union[
        Annotated[AcceptPropertyItem, Tag("accept")],
        Annotated[RejectPropertyItem, Tag("reject")],
        Annotated[CreatePropertyItem, Tag("create")],
    ],
    Discriminator("action"),
]


class PatchPropertiesRequest(BaseModel):
    """Request body for PATCH /politicians/{qid}/properties."""

    items: List[PropertyActionItem]


class SourcePatchPropertiesRequest(BaseModel):
    """Request body for PATCH /archived-pages/{id}/properties.

    Items keyed by politician QID, e.g.:
    {"Q123": [{"action": "accept", "id": "..."}, ...]}
    """

    items: Dict[str, List[PropertyActionItem]]


class PatchPropertiesResponse(BaseModel):
    """Response for property evaluation endpoints."""

    success: bool
    message: str
    errors: List[str] = []


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

"""Pydantic schemas for API responses."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    field_serializer,
    field_validator,
)

from ..models import PropertyType


class UUIDBaseModel(BaseModel):
    """Base model with automatic UUID to string serialization."""

    @field_serializer("id", when_used="always", check_fields=False)
    def serialize_uuid(self, value: UUID) -> str:
        return str(value) if value else None

    model_config = ConfigDict(from_attributes=True)


class SourceResponse(UUIDBaseModel):
    """Schema for source data."""

    id: UUID
    url: str
    url_hash: str | None = None
    fetch_timestamp: datetime | None = None
    status: str
    error: str | None = None
    http_status_code: int | None = None
    language_qids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("language_qids", "source_languages"),
    )

    @field_validator("language_qids", mode="before")
    @classmethod
    def extract_language_qids(cls, v):
        if v is None:
            return []
        if isinstance(v, list) and v and hasattr(v[0], "language_id"):
            return [link.language_id for link in v]
        return v

    @field_validator("status", "error", mode="before")
    @classmethod
    def coerce_enum_value(cls, v):
        if v is None:
            return None
        if hasattr(v, "value"):
            return v.value
        return v


class PropertyReferenceResponse(UUIDBaseModel):
    """Schema for a property reference (evidence source)."""

    id: UUID
    source: SourceResponse
    supporting_quotes: list[str] | None = None


class PropertyResponse(UUIDBaseModel):
    """Unified property response."""

    id: UUID
    type: PropertyType
    value: str | None = None
    value_precision: int | None = None
    entity_id: str | None = None
    entity_name: str | None = None  # Add for frontend convenience
    statement_id: str | None = None
    qualifiers: dict[str, Any] | None = None
    references: list[dict[str, Any]] | None = None
    sources: list[PropertyReferenceResponse] = []

    @field_serializer("type")
    def serialize_property_type(self, value: PropertyType) -> str:
        """Return enum value (Wikidata P... identifier) instead of name."""
        return value.value if value else None


class PoliticianResponse(UUIDBaseModel):
    """Simplified politician response."""

    id: UUID
    name: str
    wikidata_id: str | None = None
    sources: list[SourceResponse] = []
    properties: list[PropertyResponse]  # Single flat list


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment status for empty state UX."""

    has_enrichable_politicians: bool


class NextPoliticianResponse(BaseModel):
    """Response for next politician endpoint - lightweight, returns only QID."""

    wikidata_id: str | None = None
    meta: EnrichmentMetadata


class AcceptPropertyItem(BaseModel):
    action: Literal["accept"]
    id: UUID


class RejectPropertyItem(BaseModel):
    action: Literal["reject"]
    id: UUID


class SkipPropertyItem(BaseModel):
    action: Literal["skip"]
    id: UUID


class CreatePropertyItem(BaseModel):
    action: Literal["create"]
    type: str
    value: str | None = None
    value_precision: int | None = None
    entity_id: str | None = None
    qualifiers: dict[str, Any] | None = None


PropertyActionItem = Annotated[
    Annotated[AcceptPropertyItem, Tag("accept")]
    | Annotated[RejectPropertyItem, Tag("reject")]
    | Annotated[SkipPropertyItem, Tag("skip")]
    | Annotated[CreatePropertyItem, Tag("create")],
    Discriminator("action"),
]


class PatchPropertiesRequest(BaseModel):
    """Request body for PATCH /politicians/{qid}/properties."""

    items: list[PropertyActionItem]


class PatchPropertiesResponse(BaseModel):
    """Response for property evaluation endpoints."""

    success: bool
    message: str
    errors: list[str] = []


class CreateSourceRequest(BaseModel):
    """Request body for POST /politicians/{qid}/sources."""

    url: str


class CreatePoliticianRequest(BaseModel):
    """Request body for POST /politicians."""

    name: str


class CreatePoliticianResponse(BaseModel):
    """Response for POST /politicians."""

    success: bool
    wikidata_id: str | None = None
    message: str
    errors: list[str] = []


class LanguageResponse(BaseModel):
    """Schema for language response."""

    wikidata_id: str
    name: str
    description: str | None = None
    iso_639_1: str | None = None
    iso_639_3: str | None = None
    sources_count: int

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    """Schema for country response."""

    wikidata_id: str
    name: str
    description: str | None = None
    citizenships_count: int

    model_config = ConfigDict(from_attributes=True)


class EntitySearchResponse(BaseModel):
    """Unified schema for entity search results."""

    wikidata_id: str
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserSettingsResponse(BaseModel):
    """User settings (typed booleans) for GET /settings."""

    advanced_mode: bool = False
    basic_tutorial_completed: bool = False
    advanced_tutorial_completed: bool = False
    stats_unlocked: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserSettingsPatch(BaseModel):
    """Partial settings update body for PATCH /settings."""

    advanced_mode: bool | None = None
    basic_tutorial_completed: bool | None = None
    advanced_tutorial_completed: bool | None = None
    stats_unlocked: bool | None = None

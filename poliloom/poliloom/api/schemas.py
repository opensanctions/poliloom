"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from ..models import ActionKind


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


class TermMaps(BaseModel):
    """Language-keyed term maps of a Wikidata entity."""

    labels: dict[str, str]
    descriptions: dict[str, str]
    aliases: dict[str, list[str]]


class StatementResponse(UUIDBaseModel):
    """Cached Wikidata statement document shown as review context."""

    id: UUID
    document: dict
    entity_terms: TermMaps | None = None  # Terms of the statement's value entity


class ActionEvidenceResponse(UUIDBaseModel):
    """Evidence linking an action to a source."""

    id: UUID
    source: SourceResponse
    supporting_quotes: list[str] | None = None


class ActionResponse(UUIDBaseModel):
    """Proposed Wikidata operation pending or undergoing review."""

    id: UUID
    kind: str
    statement_id: UUID | None = None  # Target statement for edits
    payload: dict
    entity_terms: TermMaps | None = None  # Terms of the action's value entity
    evidence: list[ActionEvidenceResponse] = []
    is_accepted: bool | None = None
    applied_at: datetime | None = None
    error: str | None = None


class PoliticianResponse(UUIDBaseModel):
    """Politician with context statements and reviewable actions."""

    id: UUID
    wikidata_id: str | None = None
    terms: TermMaps
    sources: list[SourceResponse] = []
    statements: list[StatementResponse] = []
    actions: list[ActionResponse] = []


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment status for empty state UX."""

    has_enrichable_politicians: bool


class NextPoliticianResponse(BaseModel):
    """Response for next politician endpoint - lightweight, returns only QID."""

    wikidata_id: str | None = None
    meta: EnrichmentMetadata


class SubmittedAction(BaseModel):
    """A submitted action: an existing pending action or a user-authored new one."""

    id: UUID | None = None  # Existing action; None = user-authored new action
    kind: ActionKind
    statement_id: UUID | None = None  # Target statement; required for EDIT_STATEMENT
    payload: dict  # CREATE: {"statement": {...}}; EDIT: {"patch": [...]}
    is_accepted: bool


class PatchActionsRequest(BaseModel):
    """Request body for PATCH /politicians/{qid}/actions."""

    actions: list[SubmittedAction]
    skips: list[UUID] = []  # Action IDs to skip for this user


class PatchActionsResponse(BaseModel):
    """Response for action decision endpoints."""

    success: bool
    message: str
    errors: list[str] = []


class CreateSourceRequest(BaseModel):
    """Request body for POST /politicians/{qid}/sources."""

    url: str


class LanguageResponse(BaseModel):
    """Schema for language response."""

    wikidata_id: str
    terms: TermMaps
    wikimedia_code: str | None = None
    iso_639_1: str | None = None
    iso_639_3: str | None = None
    sources_count: int

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    """Schema for country response."""

    wikidata_id: str
    terms: TermMaps
    citizenships_count: int

    model_config = ConfigDict(from_attributes=True)


class EntitySearchResponse(BaseModel):
    """Unified schema for entity search results."""

    wikidata_id: str
    terms: TermMaps

    model_config = ConfigDict(from_attributes=True)


class UserSettingsResponse(BaseModel):
    """User settings (typed booleans) for GET /settings."""

    advanced_mode: bool = False
    basic_tutorial_completed: bool = False
    advanced_tutorial_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserSettingsPatch(BaseModel):
    """Partial settings update body for PATCH /settings."""

    advanced_mode: bool | None = None
    basic_tutorial_completed: bool | None = None
    advanced_tutorial_completed: bool | None = None

"""Pydantic schemas for API responses."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
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
        """Return enum value (Wikidata P... identifier) instead of name."""
        return value.value if value else None


class PoliticianResponse(UUIDBaseModel):
    """Simplified politician response."""

    id: UUID
    name: str
    wikidata_id: Optional[str] = None
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


class EvaluationObjectResponse(UUIDBaseModel):
    """Schema for a single evaluation object."""

    id: UUID
    user_id: str
    is_confirmed: bool
    property_id: UUID
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "98765432-4321-4321-4321-210987654321",
                "user_id": "12345",
                "is_confirmed": True,
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
                        "is_confirmed": True,
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
    description: str
    iso1_code: Optional[str] = None
    iso3_code: Optional[str] = None
    sources_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    """Schema for country response."""

    wikidata_id: str
    name: str
    description: str
    iso_code: Optional[str] = None
    citizenships_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PositionResponse(BaseModel):
    """Schema for position response."""

    wikidata_id: str
    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class LocationResponse(BaseModel):
    """Schema for location response."""

    wikidata_id: str
    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class PropertyCreateRequest(BaseModel):
    """Schema for creating a single property."""

    type: str  # PropertyType value (e.g., "P569", "P570")
    value: Optional[str] = None  # For date properties
    value_precision: Optional[int] = (
        None  # For date properties (9=year, 10=month, 11=day)
    )
    entity_id: Optional[str] = (
        None  # For entity relationships (birthplace, position, citizenship)
    )
    qualifiers_json: Optional[Dict[str, Any]] = None
    references_json: Optional[List[Dict[str, Any]]] = None

    @field_validator("type")
    @classmethod
    def validate_property_type(cls, v: str) -> str:
        """Validate that type is a valid PropertyType."""
        valid_types = [pt.value for pt in PropertyType]
        if v not in valid_types:
            raise ValueError(
                f"Invalid property type: {v}. Must be one of: {', '.join(valid_types)}"
            )
        return v

    @field_validator("value_precision")
    @classmethod
    def validate_precision(cls, v: Optional[int]) -> Optional[int]:
        """Validate that precision is valid Wikidata precision (9-11)."""
        if v is not None and v not in [9, 10, 11]:
            raise ValueError(
                "value_precision must be 9 (year), 10 (month), or 11 (day)"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Validate property constraints after initialization."""
        prop_type = PropertyType(self.type)

        # Date properties must have value and precision
        if prop_type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            if self.value is None or self.value_precision is None:
                raise ValueError(
                    f"Date properties ({self.type}) must have both value and value_precision"
                )
            if self.entity_id is not None:
                raise ValueError(f"Date properties ({self.type}) cannot have entity_id")

        # Entity properties must have entity_id
        elif prop_type in [
            PropertyType.BIRTHPLACE,
            PropertyType.POSITION,
            PropertyType.CITIZENSHIP,
        ]:
            if self.entity_id is None:
                raise ValueError(f"Entity properties ({self.type}) must have entity_id")
            if self.value is not None:
                raise ValueError(f"Entity properties ({self.type}) cannot have value")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "P569",
                "value": "+1962-00-00T00:00:00Z",
                "value_precision": 9,
            }
        }
    )


class PoliticianItem(BaseModel):
    """Schema for a single politician to create.

    Note: wikidata_id is not required on creation. It will be obtained from
    Wikidata API/dumps later when the politician is created in Wikidata.
    """

    name: str
    labels: Optional[List[str]] = None
    description: Optional[str] = None
    properties: List[PropertyCreateRequest] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "labels": ["Jane Doe", "J. Doe"],
                "description": "American politician",
                "properties": [
                    {
                        "type": "P569",
                        "value": "+1962-00-00T00:00:00Z",
                        "value_precision": 9,
                    },
                    {"type": "P19", "entity_id": "Q60"},
                ],
            }
        }
    )


class PoliticianCreateRequest(BaseModel):
    """Schema for creating multiple politicians in batch."""

    politicians: List[PoliticianItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "politicians": [
                    {
                        "name": "Jane Doe",
                        "labels": ["Jane Doe", "J. Doe"],
                        "description": "American politician",
                        "properties": [
                            {
                                "type": "P569",
                                "value": "+1962-00-00T00:00:00Z",
                                "value_precision": 9,
                            },
                            {"type": "P19", "entity_id": "Q60"},
                        ],
                    }
                ]
            }
        }
    )


class PoliticianCreateResponse(UUIDBaseModel):
    """Schema for batch politician creation response."""

    success: bool
    message: str
    politicians: List[PoliticianResponse] = []
    errors: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully created 2 politicians",
                "politicians": [
                    {
                        "id": "12345678-1234-1234-1234-123456789012",
                        "name": "Jane Doe",
                        "wikidata_id": None,
                        "properties": [
                            {
                                "id": "87654321-4321-4321-4321-210987654321",
                                "type": "P569",
                                "value": "+1962-00-00T00:00:00Z",
                                "value_precision": 9,
                                "entity_id": None,
                                "entity_name": None,
                                "proof_line": None,
                                "statement_id": None,
                                "qualifiers": None,
                                "references": None,
                                "archived_page": None,
                            }
                        ],
                    }
                ],
                "errors": [],
            }
        }
    )


class PropertyAddRequest(BaseModel):
    """Schema for adding properties to an existing politician."""

    properties: List[PropertyCreateRequest]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "properties": [
                    {
                        "type": "P569",
                        "value": "+1962-00-00T00:00:00Z",
                        "value_precision": 9,
                    },
                    {"type": "P19", "entity_id": "Q60"},
                ]
            }
        }
    )


class PropertyAddResponse(UUIDBaseModel):
    """Schema for property addition response."""

    success: bool
    message: str
    properties: List[PropertyResponse] = []
    errors: List[str] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully added 2 properties",
                "properties": [
                    {
                        "id": "87654321-4321-4321-4321-210987654321",
                        "type": "P569",
                        "value": "+1962-00-00T00:00:00Z",
                        "value_precision": 9,
                        "entity_id": None,
                        "entity_name": None,
                        "proof_line": None,
                        "statement_id": None,
                        "qualifiers": None,
                        "references": None,
                        "archived_page": None,
                    }
                ],
                "errors": [],
            }
        }
    )

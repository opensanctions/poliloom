"""PoliLoom models package - organized by domain."""

# Base classes and utilities
from .base import (
    Base,
    EntityCreationMixin,
    LanguageCodeMixin,
    PreferenceType,
    PropertyType,
    RelationType,
    SoftDeleteMixin,
    TimestampMixin,
    UpsertMixin,
)

# Wikidata infrastructure
from .wikidata import (
    CurrentImportEntity,
    CurrentImportStatement,
    WikidataEntity,
    WikidataEntityLabel,
    WikidataEntityMixin,
    WikidataDump,
    WikidataRelation,
)

# Supporting entities
from .entities import Country, Language, Location, Position

# User interaction
from .user import Evaluation, Preference

# Politician domain
from .politician import ArchivedPage, Politician, Property, WikipediaLink

__all__ = [
    # Base
    "Base",
    "EntityCreationMixin",
    "LanguageCodeMixin",
    "PreferenceType",
    "PropertyType",
    "RelationType",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UpsertMixin",
    "WikidataEntityMixin",
    # Wikidata
    "CurrentImportEntity",
    "CurrentImportStatement",
    "WikidataEntity",
    "WikidataEntityLabel",
    "WikidataDump",
    "WikidataRelation",
    # Entities
    "Country",
    "Language",
    "Location",
    "Position",
    # User
    "Evaluation",
    "Preference",
    # Politician
    "ArchivedPage",
    "Politician",
    "Property",
    "WikipediaLink",
]

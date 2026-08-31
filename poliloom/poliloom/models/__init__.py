"""PoliLoom models package - organized by domain."""

# Base classes and utilities
from .base import (
    Base,
    EntityCreationMixin,
    LanguageCodeMixin,
    PropertyComparisonResult,
    PropertyType,
    RelationType,
    SoftDeleteMixin,
    TimestampMixin,
    UpsertMixin,
)

# Supporting entities
from .entities import Country, Language, Location, Position, WikipediaProject

# Politician domain
from .politician import (
    Politician,
    WikipediaLink,
)

# Property domain
from .property import Property, PropertyReference

# Sources
from .source import (
    PoliticianSource,
    Source,
    SourceError,
    SourceLanguage,
    SourceStatus,
)

# User interaction
from .user import Evaluation, PropertyClaim, PropertySkip, UserSettings

# Wikidata infrastructure
from .wikidata import (
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    WikidataDump,
    WikidataEntity,
    WikidataEntityLabel,
    WikidataEntityMixin,
    WikidataRelation,
)

__all__ = [
    # Base
    "Base",
    # Entities
    "Country",
    # Wikidata
    "CurrentImportEntity",
    "CurrentImportStatement",
    "DownloadAlreadyCompleteError",
    "DownloadInProgressError",
    "EntityCreationMixin",
    # User
    "Evaluation",
    "Language",
    "LanguageCodeMixin",
    "Location",
    # Politician
    "Politician",
    "PoliticianSource",
    "Position",
    "Property",
    "PropertyClaim",
    "PropertyComparisonResult",
    "PropertyReference",
    "PropertySkip",
    "PropertyType",
    "RelationType",
    "SoftDeleteMixin",
    # Sources
    "Source",
    "SourceError",
    "SourceLanguage",
    "SourceStatus",
    "TimestampMixin",
    "UpsertMixin",
    "UserSettings",
    "WikidataDump",
    "WikidataEntity",
    "WikidataEntityLabel",
    "WikidataEntityMixin",
    "WikidataRelation",
    "WikipediaLink",
    "WikipediaProject",
]

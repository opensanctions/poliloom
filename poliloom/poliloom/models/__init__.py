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

# Wikidata infrastructure
from .wikidata import (
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    WikidataEntity,
    WikidataEntityLabel,
    WikidataEntityMixin,
    WikidataDump,
    WikidataRelation,
)

# Supporting entities
from .entities import Country, Language, Location, Position, WikipediaProject

# User interaction
from .user import Evaluation

# Sources
from .source import (
    Source,
    SourceError,
    SourceLanguage,
    SourceStatus,
    PoliticianSource,
)

# Politician domain
from .politician import (
    Politician,
    Property,
    PropertyReference,
    WikipediaLink,
)

__all__ = [
    # Base
    "Base",
    "EntityCreationMixin",
    "LanguageCodeMixin",
    "PropertyComparisonResult",
    "PropertyType",
    "RelationType",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UpsertMixin",
    "WikidataEntityMixin",
    # Wikidata
    "CurrentImportEntity",
    "CurrentImportStatement",
    "DownloadAlreadyCompleteError",
    "DownloadInProgressError",
    "WikidataEntity",
    "WikidataEntityLabel",
    "WikidataDump",
    "WikidataRelation",
    # Entities
    "Country",
    "Language",
    "Location",
    "Position",
    "WikipediaProject",
    # User
    "Evaluation",
    # Sources
    "Source",
    "SourceError",
    "SourceLanguage",
    "SourceStatus",
    "PoliticianSource",
    # Politician
    "Politician",
    "Property",
    "PropertyReference",
    "WikipediaLink",
]

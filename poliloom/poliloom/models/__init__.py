"""PoliLoom models package - organized by domain."""

# Action domain
from .action import Action, ActionClaim, ActionEvidence, ActionKind, ActionSkip

# Base classes and utilities
from .base import (
    Base,
    LanguageCodeMixin,
    PropertyType,
    RelationType,
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

# Sources
from .source import (
    PoliticianSource,
    Source,
    SourceError,
    SourceLanguage,
    SourceStatus,
)

# Statement domain
from .statement import Statement

# User interaction
from .user import UserSettings

# Wikidata infrastructure
from .wikidata import (
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    WikidataDump,
    WikidataEntity,
    WikidataEntityMixin,
    WikidataRelation,
)

__all__ = [
    # Actions
    "Action",
    "ActionClaim",
    "ActionEvidence",
    "ActionKind",
    "ActionSkip",
    # Base
    "Base",
    # Entities
    "Country",
    # Wikidata
    "CurrentImportEntity",
    "CurrentImportStatement",
    "DownloadAlreadyCompleteError",
    "DownloadInProgressError",
    # User
    "Language",
    "LanguageCodeMixin",
    "Location",
    # Politician
    "Politician",
    "PoliticianSource",
    "Position",
    "PropertyType",
    "RelationType",
    # Sources
    "Source",
    "SourceError",
    "SourceLanguage",
    "SourceStatus",
    "Statement",
    "TimestampMixin",
    "UpsertMixin",
    "UserSettings",
    "WikidataDump",
    "WikidataEntity",
    "WikidataEntityMixin",
    "WikidataRelation",
    "WikipediaLink",
    "WikipediaProject",
]

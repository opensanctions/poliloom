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

# Politician domain
from .politician import (
    ArchivedPage,
    ArchivedPageLanguage,
    Campaign,
    CampaignPosition,
    Politician,
    Property,
    Source,
    WikipediaSource,
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
    # Politician
    "ArchivedPage",
    "ArchivedPageLanguage",
    "Campaign",
    "CampaignPosition",
    "Politician",
    "Property",
    "Source",
    "WikipediaSource",
]

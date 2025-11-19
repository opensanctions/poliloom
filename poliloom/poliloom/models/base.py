"""Base classes, mixins, and enums for PoliLoom models."""

from datetime import datetime, timezone
from enum import Enum
from typing import List

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()


class PropertyType(str, Enum):
    """Enumeration of allowed property types for politician properties."""

    BIRTH_DATE = "P569"
    DEATH_DATE = "P570"
    BIRTHPLACE = "P19"
    POSITION = "P39"
    CITIZENSHIP = "P27"


class PreferenceType(str, Enum):
    """Enumeration of user preference types."""

    LANGUAGE = "language"
    COUNTRY = "country"


class RelationType(str, Enum):
    """Enumeration of Wikidata relation types."""

    SUBCLASS_OF = "P279"  # Subclass of relation
    INSTANCE_OF = "P31"  # Instance of relation
    PART_OF = "P361"  # Part of relation
    LOCATED_IN = "P131"  # Located in administrative territorial entity
    COUNTRY = "P17"  # Country relation
    APPLIES_TO_JURISDICTION = "P1001"  # Applies to jurisdiction relation
    OFFICIAL_LANGUAGE = "P37"  # Official language relation
    LANGUAGE_OF_WORK = "P407"  # Language of work or name relation


class TimestampMixin:
    """Mixin for adding timestamp fields."""

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for adding soft delete functionality."""

    deleted_at = Column(DateTime, nullable=True, index=True)

    def soft_delete(self):
        """Mark the entity as deleted by setting the deleted_at timestamp."""
        self.deleted_at = datetime.now(timezone.utc)


class UpsertMixin:
    """Mixin for adding batch upsert functionality."""

    # Override this in subclasses to specify which columns to update on conflict
    _upsert_update_columns = []
    # Override this in subclasses to specify the conflict columns (defaults to primary key)
    _upsert_conflict_columns = None
    # Override this in subclasses to specify the index WHERE clause for partial indexes
    _upsert_index_where = None

    @classmethod
    def upsert_batch(cls, session: Session, data: List[dict], returning_columns=None):
        """
        Upsert a batch of records.

        Args:
            session: Database session
            data: List of dicts with column data
            returning_columns: Optional list of columns to return from the upsert

        Returns:
            List of inserted/updated records if returning_columns specified, None otherwise
        """
        if not data:
            return [] if returning_columns else None

        stmt = insert(cls).values(data)

        # Use specified conflict columns or default to primary key
        conflict_columns = cls._upsert_conflict_columns
        if conflict_columns is None:
            conflict_columns = [col.name for col in cls.__table__.primary_key.columns]

        # Build conflict handling kwargs
        conflict_kwargs = {"index_elements": conflict_columns}
        if cls._upsert_index_where is not None:
            conflict_kwargs["index_where"] = cls._upsert_index_where

        # Update specified columns on conflict
        if cls._upsert_update_columns:
            update_dict = {
                col: getattr(stmt.excluded, col) for col in cls._upsert_update_columns
            }
            stmt = stmt.on_conflict_do_update(set_=update_dict, **conflict_kwargs)
        else:
            stmt = stmt.on_conflict_do_nothing(**conflict_kwargs)

        # Add RETURNING clause if requested
        if returning_columns:
            stmt = stmt.returning(*returning_columns)
            result = session.execute(stmt)
            return result.fetchall()
        else:
            session.execute(stmt)
            return None


class EntityCreationMixin:
    """Mixin for entities that can be created with their associated WikidataEntity."""

    @classmethod
    def create_with_entity(
        cls,
        session,
        wikidata_id: str,
        name: str,
        labels: List[str] = None,
        description: str = None,
    ):
        """Create an entity with its associated WikidataEntity.

        Args:
            session: Database session
            wikidata_id: Wikidata ID for the entity
            name: Name of the entity
            labels: Optional list of labels/aliases for the entity
            description: Optional description for the entity

        Returns:
            The created entity instance (other properties can be set after creation)
        """
        # Import here to avoid circular dependency
        from .wikidata import WikidataEntity, WikidataEntityLabel

        # Create WikidataEntity first (without labels - they're in separate table now)
        wikidata_entity = WikidataEntity(
            wikidata_id=wikidata_id,
            name=name,
            description=description,
        )
        session.add(wikidata_entity)

        # Create WikidataEntityLabel records if labels provided
        if labels:
            for label in labels:
                label_record = WikidataEntityLabel(
                    entity_id=wikidata_id,
                    label=label,
                )
                session.add(label_record)

        # Create the entity instance
        entity = cls(wikidata_id=wikidata_id)
        session.add(entity)

        return entity


class LanguageCodeMixin:
    """Mixin for adding language code fields."""

    iso1_code = Column(String, index=True)  # ISO 639-1 language code (2 characters)
    iso3_code = Column(String, index=True)  # ISO 639-3 language code (3 characters)
    wikimedia_code = Column(String, index=True)  # P424 Wikimedia language code

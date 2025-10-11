"""Base classes, mixins, and enums for PoliLoom models."""

from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import List

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, declarative_base, declared_attr, relationship

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


class WikidataEntityMixin:
    """Mixin for entities that have a wikidata_id and wikidata_entity relationship."""

    @declared_attr
    def wikidata_id(cls):
        return Column(
            String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
        )

    @declared_attr
    def wikidata_entity(cls):
        return relationship("WikidataEntity", lazy="joined")

    @property
    def name(self) -> str:
        """Get the name from the associated WikidataEntity."""
        return self.wikidata_entity.name

    @property
    def description(self) -> str:
        """Build rich description from WikidataRelations dynamically.

        Returns:
            Rich description string built from relations
        """

        if not hasattr(self, "wikidata_entity") or not self.wikidata_entity:
            return ""

        # Use preloaded relations instead of querying database
        relations = self.wikidata_entity.parent_relations

        # Group relations by type using defaultdict
        relations_by_type = defaultdict(list)
        for relation in relations:
            if relation.parent_entity and relation.parent_entity.name:
                relations_by_type[relation.relation_type].append(
                    relation.parent_entity.name
                )

        description_parts = []

        # Add Wikidata description if available
        if self.wikidata_entity.description:
            description_parts.append(self.wikidata_entity.description)

        # Build description based on available relations
        if relations_by_type[RelationType.INSTANCE_OF]:
            instances = relations_by_type[RelationType.INSTANCE_OF]
            description_parts.append(", ".join(instances))

        if relations_by_type[RelationType.SUBCLASS_OF]:
            subclasses = relations_by_type[RelationType.SUBCLASS_OF]
            description_parts.append(f"subclass of {', '.join(subclasses)}")

        if relations_by_type[RelationType.PART_OF]:
            parts = relations_by_type[RelationType.PART_OF]
            description_parts.append(f"part of {', '.join(parts)}")

        if relations_by_type[RelationType.APPLIES_TO_JURISDICTION]:
            jurisdictions = relations_by_type[RelationType.APPLIES_TO_JURISDICTION]
            description_parts.append(
                f"applies to jurisdiction {', '.join(jurisdictions)}"
            )

        if relations_by_type[RelationType.LOCATED_IN]:
            locations = relations_by_type[RelationType.LOCATED_IN]
            description_parts.append(f"located in {', '.join(locations)}")

        if relations_by_type[RelationType.COUNTRY]:
            countries = relations_by_type[RelationType.COUNTRY]
            description_parts.append(f"country {', '.join(countries)}")

        return ", ".join(description_parts) if description_parts else ""

    @classmethod
    def search_by_label(cls, query, search_text: str, session: Session = None):
        """Apply label search filter to an entity query using fuzzy text matching.

        Uses pg_trgm GIN index with % operator for filtering and <-> distance operator
        for ordering. Dynamically adjusts similarity threshold based on search length.

        Args:
            query: Existing select statement for entities
            search_text: Text to search for using fuzzy matching
            session: Database session for setting similarity threshold

        Returns:
            Modified query with CTE joined and ordered by similarity
        """
        # Import here to avoid circular dependency
        from .wikidata import WikidataEntityLabel

        # Set pg_trgm similarity threshold based on search length
        # Shorter terms need stricter thresholds to avoid scanning too many labels
        if session:
            search_len = len(search_text)
            if search_len <= 3:
                threshold = 0.7
            elif search_len <= 5:
                threshold = 0.5
            else:
                threshold = 0.3
            session.execute(text(f"SELECT set_limit({threshold})"))

        # CTE: Find minimum distance (maximum similarity) for each entity
        # Filters labels first, then joins to entities afterward for better performance
        min_distance = (
            select(
                WikidataEntityLabel.entity_id,
                func.min(WikidataEntityLabel.label.op("<->")(search_text)).label(
                    "min_dist"
                ),
            )
            # Use %% operator to filter - %% is escaped for pg8000 (becomes % in SQL)
            # This uses the GIN index for fast filtering
            .where(WikidataEntityLabel.label.op("%%")(search_text))
            .group_by(WikidataEntityLabel.entity_id)
            .cte("min_distance")
        )

        # Join the CTE to filter entities by search match and order by distance (ascending = most similar first)
        query = query.join(
            min_distance, cls.wikidata_id == min_distance.c.entity_id
        ).order_by(min_distance.c.min_dist.asc())

        return query


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

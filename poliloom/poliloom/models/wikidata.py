"""Wikidata entity models for hierarchy and relationship tracking."""

from collections import defaultdict
from datetime import datetime
from typing import List, Set

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Enum as SQLEnum,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, declared_attr, relationship

from .base import (
    Base,
    RelationType,
    SoftDeleteMixin,
    TimestampMixin,
    UpsertMixin,
)


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
    def search_by_label(cls, query, search_text: str):
        """Apply label search filter to an entity query using fuzzy text matching.

        Uses DISTINCT ON with word_similarity to efficiently find matches.
        word_similarity is more selective than similarity for short queries,
        reducing the number of candidates that need similarity calculation.

        Args:
            query: Existing select statement for entities
            search_text: Text to search for using fuzzy matching

        Returns:
            Modified query with CTE joined and ordered by similarity (desc = most similar first)
        """
        # Use word_similarity for better matching on short strings
        # Then calculate full similarity for ordering
        # DISTINCT ON avoids expensive GROUP BY aggregation
        best_match = (
            select(
                WikidataEntityLabel.entity_id,
                func.similarity(WikidataEntityLabel.label, search_text).label(
                    "similarity"
                ),
            )
            # Use word_similarity operator which is stricter than % for short strings
            # %%> is escaped for pg8000 (becomes %> in SQL)
            .where(WikidataEntityLabel.label.op("%%>")(search_text))
            .distinct(WikidataEntityLabel.entity_id)
            .order_by(
                WikidataEntityLabel.entity_id,
                func.similarity(WikidataEntityLabel.label, search_text).desc(),
            )
            .cte("best_match")
        )

        # Join the CTE to filter entities by search match and order by similarity
        query = query.join(
            best_match, cls.wikidata_id == best_match.c.entity_id
        ).order_by(best_match.c.similarity.desc())

        return query


class WikidataEntity(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"
    __table_args__ = (Index("idx_wikidata_entities_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns = ["name", "description"]

    # Hierarchy configuration - single source of truth for entity hierarchies
    # Used by import_entities() and clean-entities CLI command
    HIERARCHY_CONFIG = {
        "position": {
            "roots": [
                "Q4164871",  # position
                "Q29645880",  # ambassador of a country
                "Q29645886",  # ambassador to a country
                "Q707492",  # military chief of staff
            ],
            "ignore": [
                "Q114962596",  # historical position
                "Q193622",  # order
                "Q60754876",  # grade of an order
                "Q618779",  # award
                "Q4240305",  # cross
                "Q120560",  # minor basilica
                "Q2977",  # cathedral
                "Q63187345",  # religious occupation
                "Q29982545",  # function in the Evangelical Church of Czech Brethren
                "Q12737077",  # occupation
            ],
        },
        "location": {
            "roots": [
                "Q486972",  # human settlement
                "Q82794",  # region
                "Q1306755",  # administrative centre
                "Q3257686",  # locality
                "Q48907157",  # section of populated place
            ],
            "ignore": [],
        },
        "country": {
            "roots": [
                "Q6256",  # country
                "Q3624078",  # sovereign state
                "Q20181813",  # disputed territory
                "Q1520223",  # constituent country
                "Q1489259",  # dependent territory
                "Q1048835",  # political territorial entity
            ],
            "ignore": [],
        },
        "language": {
            "roots": [
                "Q17376908",  # languoid
            ],
            "ignore": [],
        },
    }

    wikidata_id = Column(String, primary_key=True)  # Wikidata QID as primary key
    name = Column(
        String, nullable=True
    )  # Entity name from Wikidata labels (can be None)
    description = Column(
        String, nullable=True
    )  # Entity description from Wikidata descriptions (can be None)

    # Relationships
    labels_collection = relationship(
        "WikidataEntityLabel",
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    parent_relations = relationship(
        "WikidataRelation",
        foreign_keys="WikidataRelation.child_entity_id",
        back_populates="child_entity",
        cascade="all, delete-orphan",
    )
    child_relations = relationship(
        "WikidataRelation",
        foreign_keys="WikidataRelation.parent_entity_id",
        back_populates="parent_entity",
        cascade="all, delete-orphan",
    )
    politician = relationship("Politician", back_populates="wikidata_entity")
    location = relationship("Location", back_populates="wikidata_entity")
    position = relationship("Position", back_populates="wikidata_entity")
    country = relationship("Country", back_populates="wikidata_entity")
    language = relationship("Language", back_populates="wikidata_entity")

    @classmethod
    def query_hierarchy_descendants(
        cls,
        session: Session,
        root_ids: List[str],
        ignore_ids: List[str] = None,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ) -> Set[str]:
        """
        Query all descendants of multiple root entities from database using recursive SQL.
        Only returns classes that have names and excludes ignored IDs and their descendants.

        Args:
            session: Database session
            root_ids: List of root entity QIDs
            ignore_ids: List of entity QIDs to exclude along with their descendants
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)

        Returns:
            Set of all descendant QIDs (including the roots) that have names
        """
        if not root_ids:
            return set()

        ignore_ids = ignore_ids or []

        # Use recursive CTEs - one for descendants, one for ignored descendants
        sql = text(
            """
            WITH RECURSIVE descendants AS (
                -- Base case: start with all root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities
                WHERE wikidata_id = ANY(:root_ids)
                UNION
                -- Recursive case: find all children
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
                WHERE sr.relation_type = :relation_type
            ),
            ignored_descendants AS (
                -- Base case: start with ignored IDs
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities
                WHERE wikidata_id = ANY(:ignore_ids)
                UNION
                -- Recursive case: find all children of ignored IDs
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN ignored_descendants id ON sr.parent_entity_id = id.wikidata_id
                WHERE sr.relation_type = :relation_type
            )
            SELECT DISTINCT d.wikidata_id
            FROM descendants d
            JOIN wikidata_entities wc ON d.wikidata_id = wc.wikidata_id
            WHERE wc.name IS NOT NULL
            AND d.wikidata_id NOT IN (SELECT wikidata_id FROM ignored_descendants)
        """
        )

        result = session.execute(
            sql,
            {
                "root_ids": root_ids,
                "ignore_ids": ignore_ids,
                "relation_type": relation_type.name,
            },
        )
        return {row[0] for row in result.fetchall()}


class WikidataEntityLabel(Base, TimestampMixin, UpsertMixin):
    """Normalized label storage for wikidata entities."""

    __tablename__ = "wikidata_entity_labels"
    __table_args__ = (
        Index(
            "uq_wikidata_entity_labels_entity_label",
            "entity_id",
            "label",
            unique=True,
        ),
        Index(
            "idx_wikidata_entity_labels_label_gin",
            "label",
            postgresql_using="gin",
            postgresql_ops={"label": "gin_trgm_ops"},
        ),
        Index("idx_wikidata_entity_labels_entity_id", "entity_id"),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns = ["entity_id", "label"]
    _upsert_update_columns = []  # No updates needed - labels are immutable

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        nullable=False,
    )
    label = Column(Text, nullable=False)

    # Relationships
    entity = relationship("WikidataEntity", back_populates="labels_collection")


class WikidataRelation(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata relationship between entities."""

    __tablename__ = "wikidata_relations"
    __table_args__ = (Index("idx_wikidata_relations_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns = ["parent_entity_id", "child_entity_id", "relation_type"]

    parent_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type = Column(
        SQLEnum(RelationType), nullable=False, default=RelationType.SUBCLASS_OF
    )
    statement_id = Column(String, primary_key=True)

    # Relationships
    parent_entity = relationship(
        "WikidataEntity",
        foreign_keys=[parent_entity_id],
        back_populates="child_relations",
    )
    child_entity = relationship(
        "WikidataEntity",
        foreign_keys=[child_entity_id],
        back_populates="parent_relations",
    )


class WikidataDump(Base, TimestampMixin):
    """WikidataDump entity for tracking dump download and processing stages."""

    __tablename__ = "wikidata_dumps"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    url = Column(String, nullable=False)  # Full URL to the dump file
    last_modified = Column(
        DateTime, nullable=False
    )  # From HEAD request Last-Modified header

    # Processing timestamps
    downloaded_at = Column(DateTime, nullable=True)  # When download completed
    extracted_at = Column(DateTime, nullable=True)  # When extraction completed
    imported_hierarchy_at = Column(
        DateTime, nullable=True
    )  # When hierarchy import completed
    imported_entities_at = Column(
        DateTime, nullable=True
    )  # When entities import completed
    imported_politicians_at = Column(
        DateTime, nullable=True
    )  # When politicians import completed


class CurrentImportEntity(Base):
    """Temporary tracking table for entities seen during current import."""

    __tablename__ = "current_import_entities"

    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )

    @classmethod
    def cleanup_missing(
        cls, session: Session, previous_dump_timestamp: datetime
    ) -> dict:
        """
        Soft-delete entities using two-dump validation strategy.
        Only deletes entities missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added entities.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            dict: Count of entities that were soft-deleted
        """
        # Only delete if: NOT in current dump AND older than previous dump
        # Convert timezone-aware timestamp to naive for database comparison
        previous_dump_naive = previous_dump_timestamp.replace(tzinfo=None)
        deleted_result = session.execute(
            text(
                """
            UPDATE wikidata_entities
            SET deleted_at = NOW()
            WHERE wikidata_id NOT IN (SELECT entity_id FROM current_import_entities)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        return {
            "entities_marked_deleted": deleted_result.rowcount,
        }

    @classmethod
    def clear_tracking_table(cls, session: Session) -> None:
        """Clear the entity tracking table."""
        session.execute(text("TRUNCATE current_import_entities"))


class CurrentImportStatement(Base):
    """Temporary tracking table for statements seen during current import."""

    __tablename__ = "current_import_statements"

    statement_id = Column(String, primary_key=True)

    @classmethod
    def cleanup_missing(
        cls, session: Session, previous_dump_timestamp: datetime
    ) -> dict:
        """
        Soft-delete statements using two-dump validation strategy.
        Only deletes statements missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added statements.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            dict: Counts of statements that were soft-deleted
        """
        # Only delete properties if: NOT in current dump AND older than previous dump
        # Convert timezone-aware timestamp to naive for database comparison
        previous_dump_naive = previous_dump_timestamp.replace(tzinfo=None)
        properties_deleted_result = session.execute(
            text(
                """
            UPDATE properties
            SET deleted_at = NOW()
            WHERE statement_id IS NOT NULL
            AND statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        # Only delete relations if: NOT in current dump AND older than previous dump
        relations_deleted_result = session.execute(
            text(
                """
            UPDATE wikidata_relations
            SET deleted_at = NOW()
            WHERE statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        return {
            "properties_marked_deleted": properties_deleted_result.rowcount,
            "relations_marked_deleted": relations_deleted_result.rowcount,
        }

    @classmethod
    def clear_tracking_table(cls, session: Session) -> None:
        """Clear the statement tracking table."""
        session.execute(text("TRUNCATE current_import_statements"))

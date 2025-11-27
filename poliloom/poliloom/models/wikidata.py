"""Wikidata entity models for hierarchy and relationship tracking."""

from collections import defaultdict
from datetime import datetime
from typing import Set

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


def _hierarchy_cte_sql(include_ignored: bool = True) -> str:
    """Return SQL for recursive hierarchy CTEs.

    Args:
        include_ignored: Whether to include the ignored_descendants CTE

    Returns:
        SQL string with CTEs for descendants (and optionally ignored_descendants).
        Expects :root_ids, :relation_type, and optionally :ignore_ids parameters.
    """
    base_cte = """
        WITH RECURSIVE descendants AS (
            SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
            FROM wikidata_entities
            WHERE wikidata_id = ANY(:root_ids)
            UNION
            SELECT sr.child_entity_id AS wikidata_id
            FROM wikidata_relations sr
            JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
            WHERE sr.relation_type = :relation_type
        )"""

    if include_ignored:
        return (
            base_cte
            + """,
        ignored_descendants AS (
            SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
            FROM wikidata_entities
            WHERE wikidata_id = ANY(:ignore_ids)
            UNION
            SELECT sr.child_entity_id AS wikidata_id
            FROM wikidata_relations sr
            JOIN ignored_descendants id ON sr.parent_entity_id = id.wikidata_id
            WHERE sr.relation_type = :relation_type
        )"""
        )
    return base_cte


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

    # Default hierarchy configuration - override in subclasses
    _hierarchy_roots = None
    _hierarchy_ignore = None

    @classmethod
    def query_hierarchy_descendants(
        cls,
        session: Session,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ) -> Set[str]:
        """
        Query all descendants of this class's hierarchy from database using recursive SQL.
        Uses cls._hierarchy_roots and cls._hierarchy_ignore configuration.

        Args:
            session: Database session
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)

        Returns:
            Set of all descendant QIDs (including the roots)
        """
        root_ids = cls._hierarchy_roots or []
        ignore_ids = cls._hierarchy_ignore or []

        if not root_ids:
            return set()

        cte_sql = _hierarchy_cte_sql(include_ignored=True)
        sql = text(
            f"""
            {cte_sql}
            SELECT DISTINCT d.wikidata_id
            FROM descendants d
            WHERE d.wikidata_id NOT IN (SELECT wikidata_id FROM ignored_descendants)
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

    @classmethod
    def cleanup_outside_hierarchy(
        cls, session: Session, dry_run: bool = False
    ) -> dict[str, int]:
        """Remove entities outside the configured hierarchy.

        Soft-deletes properties referencing these entities (if applicable),
        then hard-deletes the entity records. Uses subqueries to avoid
        materializing large ID lists.

        Args:
            session: Database session
            dry_run: If True, only report what would be done without making changes

        Returns:
            Dict with cleanup statistics:
            - 'entities_removed': Number of entity records deleted
            - 'properties_deleted': Number of properties soft-deleted
            - 'properties_total': Total properties of this type (for percentage calc)
            - 'properties_extracted': Properties that were extracted (no statement_id)
            - 'properties_evaluated': Properties with evaluations
            - 'total_entities': Total entities before cleanup
        """
        table_name = cls.__tablename__
        prop_type = getattr(cls, "_cleanup_property_type", None)
        root_ids = getattr(cls, "_hierarchy_roots", None)
        ignore_ids = getattr(cls, "_hierarchy_ignore", None) or []

        total = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        if not root_ids:
            return {
                "entities_removed": 0,
                "properties_deleted": 0,
                "properties_total": 0,
                "properties_extracted": 0,
                "properties_evaluated": 0,
                "total_entities": total,
            }

        # Build the subquery for entities outside hierarchy
        include_ignored = bool(ignore_ids)
        cte_sql = _hierarchy_cte_sql(include_ignored=include_ignored)

        if include_ignored:
            outside_sql = f"""
                {cte_sql}
                SELECT e.wikidata_id
                FROM {table_name} e
                WHERE (
                    NOT EXISTS (
                        SELECT 1 FROM wikidata_relations wr
                        JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
                        WHERE wr.child_entity_id = e.wikidata_id
                           AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
                    )
                    OR EXISTS (
                        SELECT 1 FROM wikidata_relations wr
                        JOIN ignored_descendants ib ON wr.parent_entity_id = ib.wikidata_id
                        WHERE wr.child_entity_id = e.wikidata_id
                           AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
                    )
                )
            """
            params = {
                "root_ids": root_ids,
                "ignore_ids": ignore_ids,
                "relation_type": RelationType.SUBCLASS_OF.name,
            }
        else:
            outside_sql = f"""
                {cte_sql}
                SELECT e.wikidata_id
                FROM {table_name} e
                WHERE NOT EXISTS (
                    SELECT 1 FROM wikidata_relations wr
                    JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
                    WHERE wr.child_entity_id = e.wikidata_id
                       AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
                )
            """
            params = {
                "root_ids": root_ids,
                "relation_type": RelationType.SUBCLASS_OF.name,
            }

        # Get count of entities to remove
        to_remove_count = session.execute(
            text(f"SELECT COUNT(*) FROM ({outside_sql}) subq"), params
        ).scalar()

        stats = {
            "entities_removed": to_remove_count,
            "properties_deleted": 0,
            "properties_total": 0,
            "properties_extracted": 0,
            "properties_evaluated": 0,
            "total_entities": total,
        }

        if to_remove_count == 0:
            return stats

        if dry_run:
            if prop_type:
                prop_stats = session.execute(
                    text(f"""
                        SELECT
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE p.statement_id IS NULL) as extracted,
                            COUNT(DISTINCT e.property_id) FILTER (WHERE p.statement_id IS NULL) as evaluated,
                            (SELECT COUNT(*) FROM properties WHERE type = :prop_type AND deleted_at IS NULL) as all_props
                        FROM properties p
                        LEFT JOIN evaluations e ON e.property_id = p.id
                        WHERE p.entity_id IN ({outside_sql})
                          AND p.type = :prop_type
                          AND p.deleted_at IS NULL
                    """),
                    {**params, "prop_type": prop_type},
                ).fetchone()
                stats["properties_deleted"] = prop_stats.total
                stats["properties_total"] = prop_stats.all_props
                stats["properties_extracted"] = prop_stats.extracted
                stats["properties_evaluated"] = prop_stats.evaluated
            return stats

        # Soft-delete properties if this entity type has associated properties
        if prop_type:
            props_deleted = session.execute(
                text(f"""
                    UPDATE properties
                    SET deleted_at = NOW()
                    WHERE entity_id IN ({outside_sql})
                      AND type = :prop_type
                      AND deleted_at IS NULL
                """),
                {**params, "prop_type": prop_type},
            ).rowcount
            stats["properties_deleted"] = props_deleted

        # Hard-delete entity records
        deleted = session.execute(
            text(f"DELETE FROM {table_name} WHERE wikidata_id IN ({outside_sql})"),
            params,
        ).rowcount
        stats["entities_removed"] = deleted

        return stats


class WikidataEntity(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"
    __table_args__ = (Index("idx_wikidata_entities_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns = ["name", "description"]

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
    def cleanup_orphaned(cls, session: Session) -> int:
        """Hard-delete wikidata_entities not referenced by any entity table or property.

        Removes WikidataEntity records that are no longer needed because:
        - No politician, position, location, country, or language references them
        - No property references them as entity_id
        - No relation references them as parent of a kept entity

        Args:
            session: Database session

        Returns:
            Number of orphaned entities deleted
        """
        # Build temp table of entities to keep
        session.execute(
            text("CREATE TEMP TABLE entities_to_keep (wikidata_id VARCHAR)")
        )

        # Insert from each entity table
        session.execute(
            text("INSERT INTO entities_to_keep SELECT wikidata_id FROM politicians")
        )
        session.execute(
            text("INSERT INTO entities_to_keep SELECT wikidata_id FROM locations")
        )
        session.execute(
            text("INSERT INTO entities_to_keep SELECT wikidata_id FROM positions")
        )
        session.execute(
            text("INSERT INTO entities_to_keep SELECT wikidata_id FROM countries")
        )
        session.execute(
            text("INSERT INTO entities_to_keep SELECT wikidata_id FROM languages")
        )

        # Keep entities referenced by properties
        session.execute(
            text("""
            INSERT INTO entities_to_keep
            SELECT DISTINCT entity_id
            FROM properties
            WHERE entity_id IS NOT NULL
        """)
        )

        # Keep parent entities from relations
        session.execute(
            text("""
            INSERT INTO entities_to_keep
            SELECT DISTINCT parent_entity_id
            FROM wikidata_relations
            WHERE child_entity_id IN (
                SELECT wikidata_id FROM politicians
                UNION ALL
                SELECT wikidata_id FROM locations
                UNION ALL
                SELECT wikidata_id FROM positions
                UNION ALL
                SELECT wikidata_id FROM countries
                UNION ALL
                SELECT wikidata_id FROM languages
            )
        """)
        )

        # Create index for efficient lookup
        session.execute(
            text(
                "CREATE INDEX idx_temp_entities_to_keep ON entities_to_keep(wikidata_id)"
            )
        )

        # Delete entities not in keep list
        result = session.execute(
            text("""
            DELETE FROM wikidata_entities
            WHERE NOT EXISTS (
                SELECT 1 FROM entities_to_keep
                WHERE entities_to_keep.wikidata_id = wikidata_entities.wikidata_id
            )
        """)
        )

        # Clean up temp table
        session.execute(text("DROP TABLE entities_to_keep"))

        return result.rowcount


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
    __table_args__ = (
        Index("idx_wikidata_relations_updated_at", "updated_at"),
        Index(
            "idx_wikidata_relations_child_relation",
            "child_entity_id",
            "relation_type",
        ),
    )

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

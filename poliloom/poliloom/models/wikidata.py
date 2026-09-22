"""Wikidata entity models for hierarchy and relationship tracking."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    and_,
    cast,
    delete,
    exists,
    func,
    literal,
    literal_column,
    or_,
    select,
    text,
    true,
    union_all,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session, declared_attr, relationship

from poliloom import search
from poliloom.wikidata.terms import resolve_label

from .action import Action, ActionKind
from .base import (
    Base,
    RelationType,
    TimestampMixin,
    UpsertMixin,
)
from .statement import Statement


class WikidataEntityMixin:
    """Mixin for entities that have a wikidata_id and wikidata_entity relationship."""

    _search_indexed = False

    @declared_attr
    def wikidata_id(cls):
        return Column(
            String,
            ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
            primary_key=True,
        )

    @declared_attr
    def wikidata_entity(cls):
        return relationship("WikidataEntity", lazy="joined")

    @property
    def description(self) -> str:
        """Build rich description from WikidataRelations dynamically.

        Resolves the entity's own description and its relation parents' names
        from the language-keyed term maps.

        Returns:
            Rich description string built from relations
        """

        if not self.wikidata_entity:
            return ""

        # Use preloaded relations instead of querying database
        relations = self.wikidata_entity.parent_relations

        # Group relations by type using defaultdict
        relations_by_type = defaultdict(list)
        for relation in relations:
            parent = relation.parent_entity
            parent_label = parent.resolved_label if parent else None
            if parent_label:
                relations_by_type[relation.relation_type].append(parent_label)

        description_parts = []

        # Add Wikidata description if available
        entity_description = resolve_label(self.wikidata_entity.descriptions)
        if entity_description:
            description_parts.append(entity_description)

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
    def find_similar(
        cls,
        query: str,
        limit: int = 100,
    ) -> list[str]:
        """Find similar entities by searching the search index.

        Args:
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of wikidata_ids ordered by relevance
        """
        return search.search(
            query,
            entity_type=cls.__name__,
            limit=limit,
        )

    # Default hierarchy configuration - override in subclasses
    _hierarchy_roots = None
    _hierarchy_ignore = None

    @classmethod
    def _build_descendants_cte(
        cls,
        root_ids: list[str],
        relation_type: RelationType = RelationType.SUBCLASS_OF,
        cte_name: str = "descendants",
    ):
        """Build a recursive CTE for hierarchy descendants using SQLAlchemy.

        Args:
            root_ids: List of root entity QIDs to start from
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)
            cte_name: Name for the CTE (must be unique within a query)

        Returns:
            SQLAlchemy CTE containing all descendant wikidata_ids
        """
        # Import here to avoid circular imports
        # Base case: select root entities
        base_query = select(
            cast(WikidataEntity.wikidata_id, String).label("wikidata_id")
        ).where(WikidataEntity.wikidata_id.in_(root_ids))

        # Create the recursive CTE
        descendants = base_query.cte(cte_name, recursive=True)

        # Recursive case: join with relations to find children
        # Need to reference WikidataRelation after it's defined
        from poliloom.models.wikidata import WikidataRelation

        recursive_query = select(
            WikidataRelation.child_entity_id.label("wikidata_id")
        ).where(
            and_(
                WikidataRelation.parent_entity_id == descendants.c.wikidata_id,
                WikidataRelation.relation_type == relation_type,
            )
        )

        descendants = descendants.union(recursive_query)
        return descendants

    @classmethod
    def query_hierarchy_descendants(
        cls,
        session: Session,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ) -> set[str]:
        """
        Query all descendants of this class's hierarchy from database using recursive CTE.
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

        # Build descendants CTE
        descendants = cls._build_descendants_cte(
            root_ids, relation_type, cte_name="descendants"
        )

        # Build ignored descendants CTE if needed
        if ignore_ids:
            ignored_descendants = cls._build_descendants_cte(
                ignore_ids, relation_type, cte_name="ignored_descendants"
            )

            # Select descendants not in ignored set
            query = (
                select(descendants.c.wikidata_id)
                .distinct()
                .where(
                    ~exists(
                        select(literal_column("1")).where(
                            ignored_descendants.c.wikidata_id
                            == descendants.c.wikidata_id
                        )
                    )
                )
            )
        else:
            query = select(descendants.c.wikidata_id).distinct()

        result = session.execute(query)
        return {row[0] for row in result.fetchall()}

    @classmethod
    def query_ignored_hierarchy_descendants(
        cls,
        session: Session,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ) -> set[str]:
        """
        Query all descendants of this class's ignored hierarchy branches.
        Uses cls._hierarchy_ignore configuration.

        Args:
            session: Database session
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)

        Returns:
            Set of all ignored descendant QIDs (including the ignore roots)
        """
        ignore_ids = cls._hierarchy_ignore or []

        if not ignore_ids:
            return set()

        # Build ignored descendants CTE
        ignored_descendants = cls._build_descendants_cte(
            ignore_ids, relation_type, cte_name="ignored_descendants"
        )

        query = select(ignored_descendants.c.wikidata_id).distinct()
        result = session.execute(query)
        return {row[0] for row in result.fetchall()}

    @classmethod
    def _build_outside_hierarchy_subquery(
        cls,
        root_ids: list[str],
        ignore_ids: list[str] | None = None,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ):
        """Build a subquery for entities outside the configured hierarchy.

        Args:
            root_ids: List of root entity QIDs defining the hierarchy
            ignore_ids: Optional list of QIDs whose descendants should be excluded
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)

        Returns:
            SQLAlchemy subquery selecting wikidata_ids outside the hierarchy
        """
        from poliloom.models.wikidata import WikidataRelation

        # Build descendants CTE
        descendants = cls._build_descendants_cte(
            root_ids, relation_type, cte_name="descendants"
        )

        # Check if entity has a relation to any descendant
        in_hierarchy = exists(
            select(literal_column("1"))
            .select_from(WikidataRelation)
            .where(
                and_(
                    WikidataRelation.child_entity_id == cls.wikidata_id,
                    WikidataRelation.parent_entity_id == descendants.c.wikidata_id,
                    WikidataRelation.relation_type.in_(
                        [RelationType.INSTANCE_OF, RelationType.SUBCLASS_OF]
                    ),
                )
            )
        )

        if ignore_ids:
            # Build ignored descendants CTE
            ignored_descendants = cls._build_descendants_cte(
                ignore_ids, relation_type, cte_name="ignored_descendants"
            )

            # Check if entity is in an ignored branch
            in_ignored = exists(
                select(literal_column("1"))
                .select_from(WikidataRelation)
                .where(
                    and_(
                        WikidataRelation.child_entity_id == cls.wikidata_id,
                        WikidataRelation.parent_entity_id
                        == ignored_descendants.c.wikidata_id,
                        WikidataRelation.relation_type.in_(
                            [RelationType.INSTANCE_OF, RelationType.SUBCLASS_OF]
                        ),
                    )
                )
            )

            # Entity is outside hierarchy if: not in hierarchy OR in ignored branch
            outside_condition = or_(~in_hierarchy, in_ignored)
        else:
            outside_condition = ~in_hierarchy

        return select(cls.wikidata_id).where(outside_condition).subquery()

    @classmethod
    def preview_outside_hierarchy(
        cls,
        session: Session,
    ) -> dict[str, int]:
        """Preview what cleanup_outside_hierarchy would do without making changes.

        Returns:
            Dict with preview statistics:
            - 'entities_removed': Number of entity records that would be deleted
            - 'statements_deleted': Number of statements that would be deleted
            - 'statements_total': Total statements of this property type
            - 'total_entities': Total entities before cleanup
        """
        root_ids = cls._hierarchy_roots
        ignore_ids = cls._hierarchy_ignore or []
        property_id = getattr(cls, "_cleanup_property_type", None)
        total = session.execute(select(func.count()).select_from(cls)).scalar()

        stats = {
            "entities_removed": 0,
            "statements_deleted": 0,
            "statements_total": 0,
            "total_entities": total,
        }

        if not root_ids:
            return stats

        outside_subquery = cls._build_outside_hierarchy_subquery(
            root_ids, ignore_ids or None
        )
        stats["entities_removed"] = session.execute(
            select(func.count()).select_from(outside_subquery)
        ).scalar()

        if stats["entities_removed"] == 0:
            return stats

        if property_id:
            stats["statements_deleted"] = session.execute(
                select(func.count())
                .select_from(Statement)
                .where(
                    and_(
                        Statement.entity_id.in_(select(outside_subquery)),
                        Statement.property_id == property_id,
                    )
                )
            ).scalar()

            stats["statements_total"] = session.execute(
                select(func.count())
                .select_from(Statement)
                .where(Statement.property_id == property_id)
            ).scalar()

        return stats

    @classmethod
    def cleanup_outside_hierarchy(
        cls,
        session: Session,
    ) -> dict[str, int]:
        """Remove entities outside the configured hierarchy.

        Hard-deletes statements referencing these entities (pending edit
        actions targeting them are deleted first; decided actions keep their
        payload with statement_id nulled by the foreign key), then hard-deletes
        the entity records and removes them from the search index.

        Returns:
            Dict with cleanup statistics:
            - 'entities_removed': Number of entity records deleted
            - 'statements_deleted': Number of statements deleted
            - 'total_entities': Total entities before cleanup
        """
        root_ids = cls._hierarchy_roots
        ignore_ids = cls._hierarchy_ignore or []
        property_id = getattr(cls, "_cleanup_property_type", None)
        total = session.execute(select(func.count()).select_from(cls)).scalar()

        stats = {
            "entities_removed": 0,
            "statements_deleted": 0,
            "total_entities": total,
        }

        if not root_ids:
            return stats

        outside_subquery = cls._build_outside_hierarchy_subquery(
            root_ids, ignore_ids or None
        )

        # Hard-delete statements if this entity type has associated statements
        if property_id:
            doomed_statements = select(Statement.id).where(
                Statement.entity_id.in_(select(outside_subquery)),
                Statement.property_id == property_id,
            )
            # Pending edits can never apply once their target statement is gone
            session.execute(
                delete(Action).where(
                    Action.is_accepted.is_(None),
                    Action.kind == ActionKind.EDIT_STATEMENT,
                    Action.statement_id.in_(doomed_statements),
                )
            )
            statements_deleted = session.execute(
                delete(Statement).where(Statement.id.in_(doomed_statements))
            ).rowcount
            stats["statements_deleted"] = statements_deleted

        # Hard-delete entity records and get deleted IDs via RETURNING
        delete_stmt = (
            delete(cls)
            .where(cls.wikidata_id.in_(select(outside_subquery)))
            .returning(cls.wikidata_id)
        )
        deleted_rows = session.execute(delete_stmt).fetchall()
        deleted_ids = [row[0] for row in deleted_rows]
        stats["entities_removed"] = len(deleted_ids)

        # Clean up search index
        if deleted_ids:
            search.delete_documents(deleted_ids)

        return stats


class WikidataEntity(Base, TimestampMixin, UpsertMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"
    __table_args__ = (Index("idx_wikidata_entities_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns: ClassVar[list[str]] = [
        "labels",
        "descriptions",
        "aliases",
    ]

    wikidata_id = Column(String, primary_key=True)  # Wikidata QID as primary key
    labels = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )  # {lang: label}
    descriptions = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )  # {lang: description}
    aliases = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )  # {lang: [alias]}

    # Relationships
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

    @property
    def resolved_label(self) -> str | None:
        """Resolve a display label from the language-keyed labels map."""
        return resolve_label(self.labels)

    @classmethod
    def cleanup_orphaned(cls, session: Session) -> int:
        """Hard-delete wikidata_entities not referenced by any entity table or statement.

        Removes WikidataEntity records that are no longer needed because:
        - No politician, position, location, country, language, or wikipedia_project references them
        - No source_languages references them as language_id
        - No statement references them as entity_id
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
        session.execute(
            text(
                "INSERT INTO entities_to_keep SELECT wikidata_id FROM wikipedia_projects"
            )
        )
        session.execute(
            text(
                "INSERT INTO entities_to_keep SELECT DISTINCT language_id FROM source_languages"
            )
        )

        # Keep entities referenced by statements
        session.execute(
            text("""
            INSERT INTO entities_to_keep
            SELECT DISTINCT entity_id
            FROM statements
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
                UNION ALL
                SELECT wikidata_id FROM wikipedia_projects
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

    @classmethod
    def search_index_query(cls):
        """Build query for search index documents.

        Creates a query that returns all searchable entities with their
        aggregated types and search terms. Label and alias values from the
        JSONB term maps both feed search (aliases are never display names).

        Returns:
            SQLAlchemy select query with columns: wikidata_id, types, labels
        """
        models = [m for m in WikidataEntityMixin.__subclasses__() if m._search_indexed]

        # Build UNION of all model tables with their type names
        entity_unions = union_all(
            *[
                select(
                    model.wikidata_id.label("wikidata_id"),
                    literal(model.__name__).label("type"),
                )
                for model in models
            ]
        ).subquery("entity_types")

        # One row per label value across languages
        label_terms = (
            func.jsonb_each_text(cls.labels).table_valued("key", "value").lateral()
        )
        label_values = (
            select(
                cls.wikidata_id.label("wikidata_id"),
                label_terms.c.value.label("value"),
            )
            .select_from(cls)
            .join(label_terms, true())
        )

        # One row per alias value across languages
        alias_lang_terms = (
            func.jsonb_each(cls.aliases).table_valued("key", "value").lateral()
        )
        alias_terms = (
            func.jsonb_array_elements_text(alias_lang_terms.c.value)
            .table_valued("value")
            .lateral()
        )
        alias_values = (
            select(
                cls.wikidata_id.label("wikidata_id"),
                alias_terms.c.value.label("value"),
            )
            .select_from(cls)
            .join(alias_lang_terms, true())
            .join(alias_terms, true())
        )

        # Combined search terms per entity
        term_values = label_values.union_all(alias_values).subquery("term_values")

        # Main query: aggregate types and terms per entity
        return (
            select(
                entity_unions.c.wikidata_id,
                func.array_agg(func.distinct(entity_unions.c.type)).label("types"),
                func.array_agg(func.distinct(term_values.c.value)).label("labels"),
            )
            .select_from(entity_unions)
            .join(
                cls,
                entity_unions.c.wikidata_id == cls.wikidata_id,
            )
            .join(
                term_values,
                term_values.c.wikidata_id == entity_unions.c.wikidata_id,
            )
            .group_by(entity_unions.c.wikidata_id)
        )


class WikidataRelation(Base, TimestampMixin, UpsertMixin):
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
    _upsert_update_columns: ClassVar[list[str]] = [
        "parent_entity_id",
        "child_entity_id",
        "relation_type",
    ]

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


class DownloadAlreadyCompleteError(Exception):
    """Raised when attempting to download a dump that's already been downloaded."""


class DownloadInProgressError(Exception):
    """Raised when another download is already in progress for this dump."""

    def __init__(self, message: str, hours_elapsed: float):
        super().__init__(message)
        self.hours_elapsed = hours_elapsed


class WikidataDump(Base, TimestampMixin):
    """WikidataDump entity for tracking dump download and processing stages."""

    __tablename__ = "wikidata_dumps"

    # Default stale threshold: downloads taking longer than 24 hours are considered failed
    # (typical download time is ~10 hours)
    STALE_THRESHOLD_HOURS = 24

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    url = Column(String, nullable=False)  # Full URL to the dump file
    last_modified = Column(
        DateTime(timezone=True), nullable=False
    )  # From HEAD request Last-Modified header

    # Processing timestamps
    downloaded_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When download completed
    extracted_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When extraction completed
    imported_hierarchy_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When hierarchy import completed
    imported_entities_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When entities import completed
    imported_politicians_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When politicians import completed

    @classmethod
    def prepare_for_download(
        cls,
        session: Session,
        url: str,
        last_modified: datetime,
        force: bool = False,
    ) -> "WikidataDump":
        """Prepare a WikidataDump record for downloading.

        Handles checking for existing downloads (completed or in-progress),
        stale download detection, and record cleanup.

        Args:
            session: Database session
            url: URL of the dump file
            last_modified: Last-Modified timestamp from the server
            force: If True, bypass existing download checks

        Returns:
            WikidataDump record ready for download

        Raises:
            DownloadAlreadyCompleteError: If dump was already downloaded (and not force)
            DownloadInProgressError: If another download is in progress (and not force/stale)
        """
        from datetime import timedelta

        existing_dump = (
            session.query(cls)
            .filter(cls.url == url)
            .filter(cls.last_modified == last_modified)
            .first()
        )

        if existing_dump and not force:
            if existing_dump.downloaded_at:
                raise DownloadAlreadyCompleteError(
                    f"Dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC "
                    "already downloaded"
                )
            else:
                # Check if the download is stale
                age = datetime.now(UTC) - existing_dump.created_at
                hours_elapsed = age.total_seconds() / 3600

                if age > timedelta(hours=cls.STALE_THRESHOLD_HOURS):
                    # Stale download - clean up and allow retry
                    session.delete(existing_dump)
                    session.flush()
                    existing_dump = None
                else:
                    raise DownloadInProgressError(
                        f"Download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC "
                        "already in progress",
                        hours_elapsed=hours_elapsed,
                    )
        elif existing_dump and force:
            # Force mode - delete existing record
            session.delete(existing_dump)
            session.flush()
            existing_dump = None

        # Create new dump record
        new_dump = cls(url=url, last_modified=last_modified)
        session.add(new_dump)
        session.flush()

        return new_dump

    def mark_downloaded(self, session: Session) -> None:
        """Mark this dump as successfully downloaded.

        Args:
            session: Database session
        """

        self.downloaded_at = datetime.now(UTC)
        session.merge(self)
        session.flush()

    def cleanup_failed_download(self, session: Session) -> None:
        """Clean up this dump record after a failed download.

        Removes the record to allow future retry attempts.

        Args:
            session: Database session
        """
        session.merge(self)
        session.delete(self)
        session.flush()


class CurrentImportEntity(Base):
    """Temporary tracking table for entities seen during current import."""

    __tablename__ = "current_import_entities"

    entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        primary_key=True,
    )

    @classmethod
    def cleanup_missing(
        cls,
        session: Session,
        previous_dump_timestamp: datetime,
    ) -> int:
        """
        Hard-delete entities using two-dump validation strategy.
        Only deletes entities missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added entities.

        Referencing rows (politicians and their statements/actions/links, entity
        subclass rows, relations, source_languages, statements/actions pointing at
        the entity) cascade via foreign keys. Pending edit actions whose target
        statement only dies through the cascade are deleted first, since a pending
        edit can never apply once its target is gone.

        Also removes deleted entities from the search index.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            Number of entities that were deleted
        """
        # Only delete if: NOT in current dump AND older than previous dump
        session.execute(
            text(
                """
            DELETE FROM actions
            WHERE is_accepted IS NULL
            AND kind = 'EDIT_STATEMENT'
            AND statement_id IN (
                SELECT statements.id FROM statements
                WHERE statements.entity_id IN (
                    SELECT wikidata_id FROM wikidata_entities
                    WHERE wikidata_id NOT IN (SELECT entity_id FROM current_import_entities)
                    AND updated_at <= :previous_dump_timestamp
                )
            )
        """
            ),
            {"previous_dump_timestamp": previous_dump_timestamp},
        )

        deleted_result = session.execute(
            text(
                """
            DELETE FROM wikidata_entities
            WHERE wikidata_id NOT IN (SELECT entity_id FROM current_import_entities)
            AND updated_at <= :previous_dump_timestamp
            RETURNING wikidata_id
        """
            ),
            {"previous_dump_timestamp": previous_dump_timestamp},
        )

        deleted_ids = [row[0] for row in deleted_result.fetchall()]

        # Remove deleted entities from search index
        if deleted_ids:
            search.delete_documents(deleted_ids)

        return len(deleted_ids)

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
        Hard-delete statements and relations using two-dump validation strategy.
        Only deletes statements missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added statements.

        Pending edit actions targeting doomed statements are deleted first, since
        a pending edit can never apply once its target statement is gone; decided
        actions keep their payload with statement_id nulled by the foreign key.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            dict: Counts of statements and relations that were deleted
        """
        # A pending edit can never apply once its target statement is gone
        session.execute(
            text(
                """
            DELETE FROM actions
            WHERE is_accepted IS NULL
            AND kind = 'EDIT_STATEMENT'
            AND statement_id IN (
                SELECT id FROM statements
                WHERE wikidata_statement_id NOT IN (SELECT statement_id FROM current_import_statements)
                AND updated_at <= :previous_dump_timestamp
            )
        """
            ),
            {"previous_dump_timestamp": previous_dump_timestamp},
        )

        # Only delete statements if: NOT in current dump AND older than previous dump
        statements_deleted_result = session.execute(
            text(
                """
            DELETE FROM statements
            WHERE wikidata_statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
        """
            ),
            {"previous_dump_timestamp": previous_dump_timestamp},
        )

        # Only delete relations if: NOT in current dump AND older than previous dump
        relations_deleted_result = session.execute(
            text(
                """
            DELETE FROM wikidata_relations
            WHERE statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
        """
            ),
            {"previous_dump_timestamp": previous_dump_timestamp},
        )

        return {
            "statements_deleted": statements_deleted_result.rowcount,
            "relations_deleted": relations_deleted_result.rowcount,
        }

    @classmethod
    def clear_tracking_table(cls, session: Session) -> None:
        """Clear the statement tracking table."""
        session.execute(text("TRUNCATE current_import_statements"))

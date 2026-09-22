"""Politician domain models: Politician, WikipediaLink."""

from typing import ClassVar

from dicttoxml import dicttoxml
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import object_session, relationship

from ..wikidata.document import (
    format_timeframe,
    statement_entity_id,
    statement_property_id,
    statement_time_value,
)
from .base import (
    Base,
    EntityCreationMixin,
    PropertyType,
    TimestampMixin,
    UpsertMixin,
)
from .statement import Statement
from .wikidata import (
    WikidataEntity,
    WikidataEntityMixin,
)


class Politician(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Politician entity."""

    __tablename__ = "politicians"

    _search_indexed = True
    # UpsertMixin configuration: terms live on wikidata_entities
    _upsert_update_columns: ClassVar[list[str]] = []
    _upsert_conflict_columns: ClassVar[list[str]] = ["wikidata_id"]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Override wikidata_id from WikidataEntityMixin to not be primary key
    wikidata_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    wikidata_id_numeric = Column(Integer, nullable=True, index=True)

    def get_statements_by_types(
        self, property_types: list[PropertyType]
    ) -> list["Statement"]:
        """Get all statements of the specified property types."""
        property_ids = {property_type.value for property_type in property_types}
        return [
            statement
            for statement in self.statements
            if statement_property_id(statement.document) in property_ids
        ]

    def to_xml_context(self, focus_property_types=None) -> str:
        """Build comprehensive politician context as XML structure for LLM prompts.

        Args:
            focus_property_types: Optional list of PropertyType values to include in context.
                                If None, includes all available statements.

        Returns:
            XML formatted politician context string
        """
        context_data = {
            "name": self.wikidata_entity.resolved_label or self.wikidata_id,
            "wikidata_id": self.wikidata_id,
        }

        relevant_types = (
            focus_property_types
            if focus_property_types
            else [
                PropertyType.BIRTH_DATE,
                PropertyType.DEATH_DATE,
                PropertyType.POSITION,
                PropertyType.BIRTHPLACE,
                PropertyType.CITIZENSHIP,
            ]
        )

        statements = self.get_statements_by_types(relevant_types)
        display_names = self._statement_entity_display_names(statements)

        def by_property(*property_ids: str) -> list["Statement"]:
            return [
                statement
                for statement in statements
                if statement_property_id(statement.document) in property_ids
            ]

        # Add date statements section
        if any(
            t in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]
            for t in relevant_types
        ):
            date_items = [
                f"{statement_property_id(statement.document)}: "
                f"{statement_time_value(statement.document).to_display_string()}"
                for statement in by_property(
                    PropertyType.BIRTH_DATE.value, PropertyType.DEATH_DATE.value
                )
            ]
            if date_items:
                context_data["existing_wikidata"] = date_items

        # Add positions section
        if PropertyType.POSITION in relevant_types:
            position_items = [
                f"{display_names[statement_entity_id(statement.document)]}"
                f"{format_timeframe(statement.document)}"
                for statement in by_property(PropertyType.POSITION.value)
            ]
            if position_items:
                context_data["existing_wikidata_positions"] = position_items

        # Add birthplaces section
        if PropertyType.BIRTHPLACE in relevant_types:
            birthplace_items = [
                display_names[statement_entity_id(statement.document)]
                for statement in by_property(PropertyType.BIRTHPLACE.value)
            ]
            if birthplace_items:
                context_data["existing_wikidata_birthplaces"] = birthplace_items

        # Add citizenships section
        if PropertyType.CITIZENSHIP in relevant_types:
            citizenship_items = [
                display_names[statement_entity_id(statement.document)]
                for statement in by_property(PropertyType.CITIZENSHIP.value)
            ]
            if citizenship_items:
                context_data["existing_wikidata_citizenships"] = citizenship_items

        xml_bytes = dicttoxml(
            context_data,
            custom_root="politician_context",
            attr_type=False,
            xml_declaration=False,
        )
        return xml_bytes.decode("utf-8")

    def _statement_entity_display_names(
        self, statements: list["Statement"]
    ) -> dict[str, str]:
        """Display names of the entities pointed to by entity-valued statements."""
        entity_ids = {
            entity_id
            for entity_id in (
                statement_entity_id(statement.document) for statement in statements
            )
            if entity_id is not None
        }
        if not entity_ids:
            return {}

        entities = (
            object_session(self)
            .query(WikidataEntity)
            .filter(WikidataEntity.wikidata_id.in_(entity_ids))
            .all()
        )
        return {
            entity.wikidata_id: entity.resolved_label or entity.wikidata_id
            for entity in entities
        }

    @classmethod
    def query_base(cls):
        """
        Build base query for politicians.

        Returns:
            SQLAlchemy select statement for Politician entities
        """
        return select(cls)

    # Relationships
    wikidata_entity = relationship("WikidataEntity", back_populates="politician")
    statements = relationship(
        "Statement", back_populates="politician", cascade="all, delete-orphan"
    )
    actions = relationship(
        "Action", back_populates="politician", cascade="all, delete-orphan"
    )
    wikipedia_links = relationship(
        "WikipediaLink", back_populates="politician", cascade="all, delete-orphan"
    )
    sources = relationship(
        "Source",
        secondary="politician_sources",
        back_populates="politicians",
    )


class WikipediaLink(Base, TimestampMixin, UpsertMixin):
    """Wikipedia link entity for storing politician Wikipedia article URLs."""

    __tablename__ = "wikipedia_links"
    __table_args__ = (
        Index(
            "idx_wikipedia_links_politician_project",
            "politician_id",
            "wikipedia_project_id",
            unique=True,
        ),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns: ClassVar[list[str]] = [
        "politician_id",
        "wikipedia_project_id",
    ]
    _upsert_update_columns: ClassVar[list[str]] = ["url"]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
    )
    url = Column(String, nullable=False)
    wikipedia_project_id = Column(
        String,
        ForeignKey("wikipedia_projects.wikidata_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    politician = relationship("Politician", back_populates="wikipedia_links")
    wikipedia_project = relationship("WikipediaProject")

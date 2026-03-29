"""Property domain models: Property, PropertyReference."""

from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Session, relationship
from ..wikidata.date import WikidataDate
from .base import (
    Base,
    PropertyComparisonResult,
    PropertyType,
    SoftDeleteMixin,
    TimestampMixin,
    UpsertMixin,
)
from .source import Source


class Property(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Property entity for storing extracted politician properties."""

    statement_id = Column(String, nullable=True)
    qualifiers_json = Column(JSONB, nullable=True)  # Store all qualifiers as JSON
    references_json = Column(
        JSONB, nullable=True
    )  # Wikidata state only — from import/re-import

    __tablename__ = "properties"
    __table_args__ = (
        Index(
            "uq_properties_statement_id",
            "statement_id",
            unique=True,
            postgresql_where=Column("statement_id").isnot(None),
        ),
        Index("idx_properties_updated_at", "updated_at"),
        Index(
            "idx_properties_unevaluated",
            "politician_id",
            postgresql_where=text("statement_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "idx_properties_type_entity",
            "type",
            "entity_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_properties_citizenship_lookup",
            "politician_id",
            "type",
            "entity_id",
            postgresql_where=text("type = 'CITIZENSHIP' AND deleted_at IS NULL"),
        ),
        # Speeds up stateless politician queries checking for Wikidata citizenship
        Index(
            "idx_properties_wikidata_citizenship",
            "politician_id",
            postgresql_where=text(
                "type = 'CITIZENSHIP' AND statement_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        CheckConstraint(
            "(type IN ('BIRTH_DATE', 'DEATH_DATE') AND value IS NOT NULL AND value_precision IS NOT NULL AND entity_id IS NULL) "
            "OR (type IN ('BIRTHPLACE', 'POSITION', 'CITIZENSHIP') AND entity_id IS NOT NULL AND value IS NULL)",
            name="check_property_fields",
        ),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns = ["statement_id"]
    _upsert_index_where = text("statement_id IS NOT NULL")
    _upsert_update_columns = [
        "value",
        "value_precision",
        "entity_id",
        "qualifiers_json",
        "references_json",
    ]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(SQLEnum(PropertyType), nullable=False, index=True)
    value = Column(String, nullable=True)  # NULL for entity relationships
    value_precision = Column(
        Integer
    )  # Wikidata precision integer for date properties (9=year, 10=month, 11=day)
    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), nullable=True, index=True
    )  # For entity relationships (birthplace, position, citizenship)

    # Relationships
    politician = relationship("Politician", back_populates="properties")
    property_references = relationship(
        "PropertyReference",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    entity = relationship("WikidataEntity")
    evaluations = relationship(
        "Evaluation", back_populates="property", cascade="all, delete-orphan"
    )

    def format_timeframe(self) -> str:
        """Extract formatted date range from qualifiers_json.

        Returns:
            Formatted date range string like " (2020-01-15 - 2023-06-30)" or empty string.
            Precision-aware: shows YYYY, YYYY-MM, or YYYY-MM-DD as stored in Wikidata.
        """
        if not self.qualifiers_json:
            return ""

        start_date, end_date = self._extract_timeframe_from_qualifiers(
            self.qualifiers_json
        )

        if start_date:
            date_range = f" ({start_date.to_display_string()}"
            if end_date:
                date_range += f" - {end_date.to_display_string()})"
            else:
                date_range += " - present)"
            return date_range
        elif end_date:
            return f" (until {end_date.to_display_string()})"

        return ""

    @staticmethod
    def _extract_timeframe_from_qualifiers(
        qualifiers_json: dict | None,
    ) -> tuple[WikidataDate | None, WikidataDate | None]:
        """Extract start and end dates from position qualifiers.

        Args:
            qualifiers_json: Qualifiers dict containing P580 (start) and P582 (end)

        Returns:
            Tuple of (start_date, end_date) as WikidataDate objects or None
        """
        start_date = None
        end_date = None

        if qualifiers_json:
            if "P580" in qualifiers_json:
                start_data = qualifiers_json["P580"][0]["datavalue"]["value"]
                start_date = WikidataDate.from_wikidata_time(
                    start_data["time"], start_data["precision"]
                )
            if "P582" in qualifiers_json:
                end_data = qualifiers_json["P582"][0]["datavalue"]["value"]
                end_date = WikidataDate.from_wikidata_time(
                    end_data["time"], end_data["precision"]
                )

        return start_date, end_date

    def _compare_to(self, other: "Property") -> PropertyComparisonResult:
        """Compare this property to another to determine if they match and which is more precise.

        Args:
            other: Another Property to compare against

        Returns:
            PropertyComparisonResult indicating match status and precision comparison
        """
        # Must be same type
        if self.type != other.type:
            return PropertyComparisonResult.NO_MATCH

        if self.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            # For date properties, compare values
            self_date = WikidataDate.from_wikidata_time(
                self.value, self.value_precision
            )
            other_date = WikidataDate.from_wikidata_time(
                other.value, other.value_precision
            )

            if not WikidataDate.dates_could_be_same(self_date, other_date):
                return PropertyComparisonResult.NO_MATCH

            more_precise = WikidataDate.more_precise_date(self_date, other_date)
            if more_precise is None:
                return PropertyComparisonResult.EQUAL
            if more_precise == self_date:
                return PropertyComparisonResult.SELF_MORE_PRECISE
            return PropertyComparisonResult.OTHER_MORE_PRECISE

        elif self.type == PropertyType.POSITION:
            # For positions, must have same entity_id
            if self.entity_id != other.entity_id:
                return PropertyComparisonResult.NO_MATCH

            # Compare timeframes
            self_start, self_end = self._extract_timeframe_from_qualifiers(
                self.qualifiers_json
            )
            other_start, other_end = self._extract_timeframe_from_qualifiers(
                other.qualifiers_json
            )

            # Special case: position with dates is considered more precise than without
            # Must check this before dates_could_be_same since None vs date returns False
            self_has_dates = self_start is not None or self_end is not None
            other_has_dates = other_start is not None or other_end is not None
            if self_has_dates and not other_has_dates:
                return PropertyComparisonResult.SELF_MORE_PRECISE
            if other_has_dates and not self_has_dates:
                return PropertyComparisonResult.OTHER_MORE_PRECISE

            # Check if timeframes could be the same
            start_same = WikidataDate.dates_could_be_same(self_start, other_start)
            end_same = WikidataDate.dates_could_be_same(self_end, other_end)

            if not (start_same and end_same):
                return PropertyComparisonResult.NO_MATCH

            # Compare precision of start and end dates
            start_more_precise = WikidataDate.more_precise_date(self_start, other_start)
            end_more_precise = WikidataDate.more_precise_date(self_end, other_end)

            # Determine overall precision comparison
            self_more_precise_start = (
                start_more_precise is not None and start_more_precise == self_start
            )
            self_more_precise_end = (
                end_more_precise is not None and end_more_precise == self_end
            )
            other_more_precise_start = (
                start_more_precise is not None and start_more_precise == other_start
            )
            other_more_precise_end = (
                end_more_precise is not None and end_more_precise == other_end
            )

            # Self is more precise if it has more precise data for at least one date
            # and other doesn't have more precise data for any date
            if (self_more_precise_start or self_more_precise_end) and not (
                other_more_precise_start or other_more_precise_end
            ):
                return PropertyComparisonResult.SELF_MORE_PRECISE
            if (other_more_precise_start or other_more_precise_end) and not (
                self_more_precise_start or self_more_precise_end
            ):
                return PropertyComparisonResult.OTHER_MORE_PRECISE

            return PropertyComparisonResult.EQUAL

        else:
            # For BIRTHPLACE, CITIZENSHIP - exact entity_id match, no precision concept
            if self.entity_id != other.entity_id:
                return PropertyComparisonResult.NO_MATCH
            return PropertyComparisonResult.EQUAL

    @classmethod
    def find_matching(
        cls,
        db: Session,
        politician_id,
        property_type: PropertyType,
        value: str | None = None,
        value_precision: int | None = None,
        entity_id: str | None = None,
        qualifiers_json: dict | None = None,
    ) -> Optional["Property"]:
        """Find an existing property that matches the given parameters.

        Uses _compare_to() to check against existing properties.
        Returns the matching Property if one exists with equal or greater precision,
        or None if no match (meaning a new property should be created).

        Args:
            db: Database session
            politician_id: UUID of the politician
            property_type: Type of property (BIRTH_DATE, POSITION, etc.)
            value: Value for date properties
            value_precision: Precision for date properties
            entity_id: Entity ID for entity-linked properties
            qualifiers_json: Qualifiers for position properties

        Returns:
            Matching Property instance or None
        """
        # Create a temporary Property object to use _compare_to
        candidate = cls(
            politician_id=politician_id,
            type=property_type,
            value=value,
            value_precision=value_precision,
            entity_id=entity_id,
            qualifiers_json=qualifiers_json,
        )

        # Query for potential matching properties
        query = db.query(cls).filter(
            cls.politician_id == politician_id,
            cls.type == property_type,
            cls.deleted_at.is_(None),
        )

        # For entity-linked properties, also filter by entity_id
        if property_type not in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            query = query.filter(cls.entity_id == entity_id)

        existing_properties = query.all()

        # Check against each existing property
        for existing in existing_properties:
            comparison = candidate._compare_to(existing)
            if comparison in [
                PropertyComparisonResult.OTHER_MORE_PRECISE,
                PropertyComparisonResult.EQUAL,
            ]:
                return existing

        return None

    def add_reference(
        self,
        db: Session,
        source: Source,
        supporting_quotes: list | None = None,
    ) -> "PropertyReference":
        """Add a PropertyReference linking this property to a source.

        Creates a new PropertyReference, or updates quotes if same source
        is already linked. Uses the unique constraint for idempotency.

        Args:
            db: Database session
            source: The source
            supporting_quotes: Optional list of supporting quote strings

        Returns:
            The created or updated PropertyReference
        """
        # Check if reference already exists for this property + source
        existing_ref = (
            db.query(PropertyReference)
            .filter(
                PropertyReference.property_id == self.id,
                PropertyReference.source_id == source.id,
            )
            .first()
        )

        if existing_ref:
            # Update quotes if provided
            if supporting_quotes:
                existing_ref.supporting_quotes = supporting_quotes
            return existing_ref

        # Create new reference using relationship objects so SQLAlchemy
        # populates both sides (e.g. source.property_references)
        # within the same flush.
        ref = PropertyReference(
            property=self,
            source=source,
            supporting_quotes=supporting_quotes,
        )
        db.add(ref)
        return ref


class PropertyReference(Base, TimestampMixin):
    """Evidence linking a Property to a Source.

    Each PropertyReference represents one independent source corroborating a fact.
    Multiple PropertyReferences can exist per Property (multiple sources for the same fact).
    """

    __tablename__ = "property_references"
    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "source_id",
            name="uq_property_ref_property_source",
        ),
        Index("idx_property_references_property_id", "property_id"),
        Index("idx_property_references_source_id", "source_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=False,
    )
    supporting_quotes = Column(ARRAY(String), nullable=True)

    # Relationships
    property = relationship("Property", back_populates="property_references")
    source = relationship("Source", back_populates="property_references")

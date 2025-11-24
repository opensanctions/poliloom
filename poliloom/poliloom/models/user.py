"""User interaction models: Evaluation and Preference."""

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Enum as SQLEnum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, PreferenceType, TimestampMixin


class Evaluation(Base, TimestampMixin):
    """Evaluation entity for tracking user evaluations of extracted properties."""

    __tablename__ = "evaluations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False)
    is_accepted = Column(Boolean, nullable=False)
    property_id = Column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )

    # Relationships
    property = relationship("Property", back_populates="evaluations")


class Preference(Base, TimestampMixin):
    """User preference entity for storing user language and country preferences."""

    __tablename__ = "preferences"
    __table_args__ = (
        Index(
            "uq_preferences_user_type_entity",
            "user_id",
            "preference_type",
            "entity_id",
            unique=True,
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False, index=True)
    preference_type = Column(SQLEnum(PreferenceType), nullable=False, index=True)
    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), nullable=False
    )

    # Relationships
    entity = relationship("WikidataEntity")

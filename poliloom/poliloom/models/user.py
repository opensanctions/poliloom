"""User interaction models: Evaluation, UserSettings, UserFilterPreference."""

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class PreferenceType(str, Enum):
    """Type of user filter preference."""

    LANGUAGE = "LANGUAGE"
    COUNTRY = "COUNTRY"


class Evaluation(Base, TimestampMixin):
    """Evaluation entity for tracking user evaluations of extracted properties."""

    __tablename__ = "evaluations"
    __table_args__ = (
        # Speeds up timeseries queries filtering by created_at
        Index("idx_evaluations_created_at", "created_at"),
        # Speeds up joins from properties to evaluations with date filtering
        Index("idx_evaluations_property_created", "property_id", "created_at"),
    )

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


class UserSettings(Base, TimestampMixin):
    """Per-user typed settings (one row per user)."""

    __tablename__ = "user_settings"

    user_id = Column(String, primary_key=True)
    advanced_mode = Column(Boolean, nullable=False, server_default=text("false"))
    basic_tutorial_completed = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    advanced_tutorial_completed = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    stats_unlocked = Column(Boolean, nullable=False, server_default=text("false"))


class UserFilterPreference(Base, TimestampMixin):
    """User's selected filter entities (language or country) by Wikidata QID."""

    __tablename__ = "user_filter_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "preference_type",
            "entity_id",
            name="uq_user_filter_user_type_entity",
        ),
        Index("ix_user_filter_user", "user_id"),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False)
    preference_type = Column(
        SAEnum(PreferenceType, name="preferencetype"), nullable=False
    )
    entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        nullable=False,
    )

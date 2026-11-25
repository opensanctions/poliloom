"""Action domain models: Action, ActionEvidence, ActionClaim, ActionSkip."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class Action(Base, TimestampMixin):
    """Statement proposal for a politician.

    Lifecycle: pending (is_accepted NULL) → accepted/discarded (TRUE/FALSE)
    → applied (applied_at set, error NULL on success).
    """

    __tablename__ = "actions"
    __table_args__ = (
        Index(
            "idx_actions_politician_pending",
            "politician_id",
            postgresql_where=text("is_accepted IS NULL"),
        ),
        Index(
            "idx_actions_target_pending",
            "target_wikidata_statement_id",
            postgresql_where=text(
                "is_accepted IS NULL AND target_wikidata_statement_id IS NOT NULL"
            ),
        ),
        Index("ix_actions_entity_id", "entity_id"),
        CheckConstraint(
            "(target_wikidata_statement_id IS NULL) = (before IS NULL) "
            "AND (before IS NULL OR jsonb_typeof(before) = 'object')",
            name="ck_actions_target_before",
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_wikidata_statement_id = Column(String, nullable=True)
    before = Column(JSONB(none_as_null=True), nullable=True)
    after = Column(JSONB(none_as_null=True), nullable=False)
    references_to_add = Column(
        JSONB(none_as_null=True), nullable=False, server_default=text("'[]'::jsonb")
    )
    applied_wikidata_statement_id = Column(String, nullable=True)
    entity_id = Column(
        String,
        Computed(
            "CASE WHEN target_wikidata_statement_id IS NULL "
            "AND \"after\" #>> '{property,id}' IN ('P19','P27','P39') "
            "THEN \"after\" #>> '{value,content}' END"
        ),
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        nullable=True,
    )
    is_accepted = Column(
        Boolean, nullable=True
    )  # NULL pending, TRUE accepted, FALSE discarded
    decided_by_user_id = Column(String, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="actions")
    evidence = relationship(
        "ActionEvidence", back_populates="action", cascade="all, delete-orphan"
    )


class ActionEvidence(Base, TimestampMixin):
    """Evidence linking an Action to a Source."""

    __tablename__ = "action_evidence"
    __table_args__ = (
        UniqueConstraint("action_id", "source_id", name="uq_action_evidence_pair"),
        Index("idx_action_evidence_action_id", "action_id"),
        Index("idx_action_evidence_source_id", "source_id"),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    action_id = Column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=False,
    )
    supporting_quotes = Column(ARRAY(String), nullable=True)

    # Relationships
    action = relationship("Action", back_populates="evidence")
    source = relationship("Source")


class ActionClaim(Base, TimestampMixin):
    """Tracks a user's current or past claim on an action for review.

    Liveness is evaluated via claimed_at for unreleased claims. Expired claims
    are released opportunistically and retained as history.
    """

    __tablename__ = "action_claims"
    __table_args__ = (
        Index(
            "uq_action_claims_unreleased_action",
            "action_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    action_id = Column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String, nullable=False, index=True)
    claimed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    released_at = Column(DateTime(timezone=True), nullable=True)


class ActionSkip(Base, TimestampMixin):
    """Tracks an action skipped by an individual user."""

    __tablename__ = "action_skips"
    __table_args__ = (UniqueConstraint("user_id", "action_id"),)

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False, index=True)
    action_id = Column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )

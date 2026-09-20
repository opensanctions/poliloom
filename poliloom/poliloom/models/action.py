"""Action domain models: Action, ActionEvidence, ActionClaim, ActionSkip."""

from enum import Enum

from sqlalchemy import (
    Boolean,
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
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ActionKind(str, Enum):
    """Kind of Wikidata operation an Action proposes."""

    CREATE_STATEMENT = "CREATE_STATEMENT"
    EDIT_STATEMENT = "EDIT_STATEMENT"


class Action(Base, TimestampMixin):
    """Proposed Wikidata operation for a politician.

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
    kind = Column(
        SQLEnum(ActionKind, native_enum=False, validate_strings=True),
        nullable=False,
    )
    statement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("statements.id"),
        nullable=True,
    )  # NULL for pending creates; target statement for edits
    payload = Column(
        JSONB, nullable=False
    )  # Create body {"statement": {...}} or edit body {"patch": [...]}
    entity_id = Column(
        String,
        Computed(
            "CASE WHEN kind = 'CREATE_STATEMENT' "
            "AND payload #>> '{statement,property,id}' IN ('P19','P27','P39') "
            "THEN payload #>> '{statement,value,content}' END"
        ),
        ForeignKey("wikidata_entities.wikidata_id"),
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
    statement = relationship("Statement")
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
    """Tracks an action currently claimed by a user for review.

    Liveness is evaluated via claimed_at; expired claims are pruned opportunistically.
    """

    __tablename__ = "action_claims"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    action_id = Column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id = Column(String, nullable=False, index=True)
    claimed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


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
        ForeignKey("actions.id"),
        nullable=False,
    )

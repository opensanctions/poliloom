"""User interaction models: Evaluation."""

from sqlalchemy import Boolean, Column, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


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

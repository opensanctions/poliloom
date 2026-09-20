"""User interaction models: UserSettings."""

from sqlalchemy import Boolean, Column, String, text

from .base import Base, TimestampMixin


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

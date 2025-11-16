"""Tests for mixin functionality."""

import time
from datetime import datetime, timezone
from uuid import UUID

from poliloom.models import Politician


class TestTimestampBehavior:
    """Test cases for timestamp mixin behavior."""

    def test_created_at_set_on_creation(self, db_session):
        """Test that created_at is set when entity is created."""
        before_create = datetime.now(timezone.utc)

        politician = Politician(name="Timestamp Test")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)
        after_create = datetime.now(timezone.utc)

        # Convert to naive UTC for comparison since SQLAlchemy returns naive datetimes
        before_create_naive = before_create.replace(tzinfo=None)
        after_create_naive = after_create.replace(tzinfo=None)
        assert before_create_naive <= politician.created_at <= after_create_naive
        # Allow for microsecond differences between created_at and updated_at
        time_diff = abs((politician.created_at - politician.updated_at).total_seconds())
        assert time_diff < 0.001  # Less than 1 millisecond difference

    def test_updated_at_changes_on_update(
        self, db_session, sample_politician, with_timestamp_triggers
    ):
        """Test that updated_at changes when entity is updated."""
        # Use fixture politician
        politician = sample_politician

        original_updated_at = politician.updated_at

        # Small delay to ensure timestamp difference

        time.sleep(0.01)

        # Update the politician
        politician.name = "Updated Name"
        db_session.commit()
        db_session.refresh(politician)

        assert politician.updated_at > original_updated_at
        assert politician.created_at < politician.updated_at


class TestUUIDBehavior:
    """Test cases for UUID mixin behavior."""

    def test_uuid_generation(self, db_session):
        """Test that UUIDs are generated automatically."""
        politician = Politician(name="UUID Test")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert politician.id is not None
        assert isinstance(politician.id, UUID)
        assert len(str(politician.id)) == 36  # Standard UUID string length

    def test_uuid_uniqueness(self, db_session):
        """Test that generated UUIDs are unique."""
        politicians = [Politician(name=f"Test Politician {i}") for i in range(10)]
        db_session.add_all(politicians)
        db_session.commit()

        # Refresh all to get their IDs
        for politician in politicians:
            db_session.refresh(politician)

        ids = [p.id for p in politicians]
        assert len(set(ids)) == len(ids)  # All IDs should be unique

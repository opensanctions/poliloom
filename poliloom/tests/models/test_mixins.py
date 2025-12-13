"""Tests for model mixins using test-only concrete models."""

from poliloom.models.base import (
    Base,
    EntityCreationMixin,
    TimestampMixin,
    UpsertMixin,
)
from poliloom.models.wikidata import WikidataEntityMixin


# Test-only model for EntityCreationMixin testing
class DummyEntity(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Test-only entity model for mixin testing."""

    __tablename__ = "test_entities"

    # UpsertMixin configuration
    _upsert_update_columns = []


class TestEntityCreationMixin:
    """Test cases for the EntityCreationMixin."""

    def test_create_with_entity_basic(self, db_session):
        """Test basic entity creation with wikidata entity."""
        entity = DummyEntity.create_with_entity(
            db_session, "Q123456", "Test Entity Name"
        )
        db_session.flush()

        assert entity.wikidata_id == "Q123456"
        assert entity.name == "Test Entity Name"
        assert entity.wikidata_entity is not None
        assert entity.wikidata_entity.wikidata_id == "Q123456"
        assert entity.wikidata_entity.name == "Test Entity Name"

    def test_create_with_entity_with_description(self, db_session):
        """Test entity creation with description."""
        entity = DummyEntity.create_with_entity(
            db_session,
            "Q123456",
            "Test Entity",
            description="A test description",
        )
        db_session.flush()

        assert entity.wikidata_entity.description == "A test description"

    def test_create_with_entity_with_labels(self, db_session):
        """Test entity creation with labels."""
        labels = ["Label 1", "Label 2", "Alias 1"]
        entity = DummyEntity.create_with_entity(
            db_session, "Q123456", "Test Entity", labels=labels
        )
        db_session.flush()

        # Verify labels were created
        assert len(entity.wikidata_entity.labels) == 3
        label_texts = [label.label for label in entity.wikidata_entity.labels]
        assert "Label 1" in label_texts
        assert "Label 2" in label_texts
        assert "Alias 1" in label_texts

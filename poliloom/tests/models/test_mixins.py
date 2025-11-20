"""Tests for model mixins using test-only concrete models."""

from sqlalchemy import select
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
        assert len(entity.wikidata_entity.labels_collection) == 3
        label_texts = [
            label.label for label in entity.wikidata_entity.labels_collection
        ]
        assert "Label 1" in label_texts
        assert "Label 2" in label_texts
        assert "Alias 1" in label_texts


class TestWikidataEntityMixinSearchByLabel:
    """Test cases for WikidataEntityMixin.search_by_label method."""

    def test_search_by_label_finds_matching_entities(self, db_session):
        """Test that label search filter finds entities with matching labels."""
        # Create entity with label
        entity = DummyEntity.create_with_entity(
            db_session, "Q123", "Test Entity", labels=["John Doe", "J. Doe"]
        )
        db_session.flush()

        query = select(DummyEntity)
        query = DummyEntity.search_by_label(query, "John")
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].wikidata_id == entity.wikidata_id

    def test_search_by_label_excludes_non_matching(self, db_session):
        """Test that label search filter excludes non-matching entities."""
        # Create entity with label
        DummyEntity.create_with_entity(
            db_session, "Q123", "Test Entity", labels=["John Doe"]
        )
        db_session.flush()

        query = select(DummyEntity)
        query = DummyEntity.search_by_label(query, "Barack Obama")
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

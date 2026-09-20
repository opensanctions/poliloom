"""Tests for model mixins using test-only concrete models."""

from typing import ClassVar

from poliloom.models.base import (
    Base,
    EntityCreationMixin,
    TimestampMixin,
    UpsertMixin,
)
from poliloom.models.wikidata import WikidataEntityMixin

from ..conftest import make_terms


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
    _upsert_update_columns: ClassVar[list[str]] = []


class TestEntityCreationMixin:
    """Test cases for the EntityCreationMixin."""

    def test_create_with_entity_basic(self, db_session):
        """Test basic entity creation with wikidata entity."""
        entity = DummyEntity.create_with_entity(
            db_session, "Q123456", make_terms("Test Entity Name")
        )
        db_session.flush()

        assert entity.wikidata_id == "Q123456"
        assert entity.wikidata_entity is not None
        assert entity.wikidata_entity.wikidata_id == "Q123456"
        assert entity.wikidata_entity.resolved_label == "Test Entity Name"

    def test_create_with_entity_with_terms(self, db_session):
        """Test entity creation with full term maps."""
        terms = {
            "labels": {"en": "Test Entity", "de": "Testentität"},
            "descriptions": {"en": "A test description"},
            "aliases": {"en": ["Test", "Tester"]},
        }
        entity = DummyEntity.create_with_entity(db_session, "Q123456", terms)
        db_session.flush()

        assert entity.wikidata_entity.labels == terms["labels"]
        assert entity.wikidata_entity.descriptions == terms["descriptions"]
        assert entity.wikidata_entity.aliases == terms["aliases"]
        assert entity.wikidata_entity.resolved_label == "Test Entity"

    def test_create_with_entity_without_terms(self, db_session):
        """Test entity creation with empty term maps."""
        entity = DummyEntity.create_with_entity(db_session, "Q123456", make_terms())
        db_session.flush()

        assert entity.wikidata_entity.labels == {}
        assert entity.wikidata_entity.resolved_label is None

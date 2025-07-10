"""Tests for the embeddings module."""

import pytest
from poliloom.embeddings import generate_embeddings_for_entities
from poliloom.models import Position, Location


class TestEmbeddingService:
    """Test cases for the generic embedding service functionality."""

    @pytest.mark.parametrize(
        "model_class,entity_name", [(Position, "positions"), (Location, "locations")]
    )
    def test_generate_embeddings_for_entities(
        self, test_session, model_class, entity_name
    ):
        """Test batch embedding generation for different entity types."""
        # Create test entities without embeddings
        entities = []
        for i in range(5):
            entity = model_class(
                name=f"Test {entity_name[:-1].title()} {i}", wikidata_id=f"Q{1000 + i}"
            )
            entities.append(entity)

        # Create one entity with embedding to ensure it's skipped
        entity_with_embedding = model_class(
            name=f"Test {entity_name[:-1].title()} With Embedding", wikidata_id="Q9999"
        )
        # Generate embedding using the module's function
        from poliloom.embeddings import generate_embedding

        entity_with_embedding.embedding = generate_embedding(entity_with_embedding.name)
        entities.append(entity_with_embedding)

        # Commit all entities
        test_session.add_all(entities)
        test_session.commit()

        # Track progress messages
        progress_messages = []

        def capture_progress(msg):
            progress_messages.append(msg)

        # Generate embeddings for entities without them
        processed_count = generate_embeddings_for_entities(
            session=test_session,
            model_class=model_class,
            entity_name=entity_name,
            batch_size=3,  # Small batch size to test batching
            progress_callback=capture_progress,
        )

        # Verify results
        assert processed_count == 5  # Only the 5 without embeddings

        # Check all entities now have embeddings
        all_entities = test_session.query(model_class).all()
        assert len(all_entities) == 6
        for entity in all_entities:
            assert entity.embedding is not None
            assert len(entity.embedding) == 384

        # Verify progress messages
        assert f"Found 5 {entity_name} without embeddings" in progress_messages
        assert "Processing in batches of 3" in progress_messages
        assert (
            f"✅ Successfully generated embeddings for 5 {entity_name}"
            in progress_messages
        )

    @pytest.mark.parametrize(
        "model_class,entity_name", [(Position, "positions"), (Location, "locations")]
    )
    def test_generate_embeddings_all_have_embeddings(
        self, test_session, model_class, entity_name
    ):
        """Test behavior when all entities already have embeddings."""
        # Create entities with embeddings
        from poliloom.embeddings import generate_embedding

        entities = []
        for i in range(3):
            entity = model_class(
                name=f"Test {entity_name[:-1].title()} {i}", wikidata_id=f"Q{2000 + i}"
            )
            entity.embedding = generate_embedding(entity.name)
            entities.append(entity)

        test_session.add_all(entities)
        test_session.commit()

        # Track progress messages
        progress_messages = []

        def capture_progress(msg):
            progress_messages.append(msg)

        # Try to generate embeddings
        processed_count = generate_embeddings_for_entities(
            session=test_session,
            model_class=model_class,
            entity_name=entity_name,
            batch_size=100,
            progress_callback=capture_progress,
        )

        # Verify no processing occurred
        assert processed_count == 0
        assert f"✅ All {entity_name} already have embeddings" in progress_messages

    def test_generate_embeddings_empty_database(self, test_session):
        """Test behavior with no entities in database."""
        progress_messages = []

        def capture_progress(msg):
            progress_messages.append(msg)

        # Test with Position
        processed_count = generate_embeddings_for_entities(
            session=test_session,
            model_class=Position,
            entity_name="positions",
            batch_size=100,
            progress_callback=capture_progress,
        )

        assert processed_count == 0
        assert "✅ All positions already have embeddings" in progress_messages

    def test_generate_embeddings_no_progress_callback(self, test_session):
        """Test that the function works without a progress callback."""
        # Create a position without embedding
        position = Position(name="Test Position", wikidata_id="Q3000")
        test_session.add(position)
        test_session.commit()

        # Generate embeddings without progress callback
        processed_count = generate_embeddings_for_entities(
            session=test_session,
            model_class=Position,
            entity_name="positions",
            batch_size=100,
            progress_callback=None,  # No callback
        )

        assert processed_count == 1

        # Verify embedding was generated
        test_session.refresh(position)
        assert position.embedding is not None
        assert len(position.embedding) == 384

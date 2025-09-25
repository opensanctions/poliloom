"""Tests for the Position model."""

from poliloom.models import Position
from poliloom import enrichment
from ..conftest import assert_model_fields


class TestPosition:
    """Test cases for the Position model."""

    def test_position_creation(self, db_session):
        """Test basic position creation."""
        position = Position.create_with_entity(db_session, "Q4416090", "Senator")
        db_session.commit()

        # Refresh with wikidata_entity loaded
        position = db_session.query(Position).filter_by(wikidata_id="Q4416090").first()

        assert_model_fields(position, {"wikidata_id": "Q4416090"})
        assert position.wikidata_entity.name == "Senator"


class TestPositionVectorSimilarity:
    """Test cases for Position vector similarity search functionality."""

    def test_embedding_deterministic_for_same_text(self):
        """Test that embedding generation is deterministic."""
        # Test deterministic behavior
        embedding1 = enrichment.generate_embedding("Prime Minister")
        embedding2 = enrichment.generate_embedding("Prime Minister")
        assert embedding1 == embedding2
        assert len(embedding1) == 384

    def test_similarity_search_functionality(
        self,
        db_session,
    ):
        """Test similarity search functionality."""
        # Create positions with embeddings
        entities_data = [
            {"wikidata_id": "Q11696", "name": "US President"},
            {"wikidata_id": "Q889821", "name": "US Governor"},
            {"wikidata_id": "Q14212", "name": "UK Prime Minister"},
        ]

        for entity_data in entities_data:
            embedding = enrichment.generate_embedding(entity_data["name"])
            position = Position.create_with_entity(
                db_session, entity_data["wikidata_id"], entity_data["name"]
            )
            position.embedding = embedding

        db_session.commit()

        # Test basic similarity search - using same session
        query_embedding = enrichment.generate_embedding("Chief Executive")
        results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )
        assert len(results) <= 2
        assert all(isinstance(pos, Position) for pos in results)

        # Test limit behavior
        no_query_embedding = enrichment.generate_embedding("Query")
        no_results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(0)
            .all()
        )
        assert no_results == []

        one_result = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(1)
            .all()
        )
        assert len(one_result) <= 1

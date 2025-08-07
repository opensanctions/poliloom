"""Test configuration and fixtures for PoliLoom tests."""

import pytest
import json
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from poliloom.models import (
    Base,
    Politician,
    WikipediaLink,
    Property,
    Position,
    HoldsPosition,
    Country,
    Location,
    ArchivedPage,
)


class MockSentenceTransformer:
    """Mock SentenceTransformer for tests."""

    def __init__(self, model_name, device=None):
        self.model_name = model_name
        self.device = device

    def encode(self, text, convert_to_tensor=False, batch_size=None):
        """Mock embedding generation for single text or batch of texts."""
        import numpy as np

        # Handle batch processing (list of texts)
        if isinstance(text, list):
            embeddings = []
            for single_text in text:
                embedding = self._generate_single_embedding(single_text)
                embeddings.append(embedding)
            return np.array(embeddings)
        else:
            # Handle single text
            return self._generate_single_embedding(text)

    def _generate_single_embedding(self, text):
        """Generate a single embedding for text."""
        import hashlib

        # Create a deterministic embedding based on text hash
        text_hash = hashlib.md5(text.encode()).digest()
        # Convert hash to numbers for embedding
        dummy_embedding = []
        for i in range(384):
            # Use hash bytes cyclically to generate 384 dimensions
            byte_val = text_hash[i % len(text_hash)]
            # Normalize to [-1, 1] range
            val = (byte_val / 127.5) - 1.0
            dummy_embedding.append(val)
        return dummy_embedding


@pytest.fixture(autouse=True)
def mock_sentence_transformers():
    """Mock sentence transformers to avoid downloading models in tests."""
    with patch("sentence_transformers.SentenceTransformer", MockSentenceTransformer):
        yield


@pytest.fixture(autouse=True)
def mock_torch():
    """Mock torch to prevent CUDA initialization in tests."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    with patch("poliloom.embeddings.torch", mock_torch):
        yield


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, "r") as f:
        return json.load(f)


@pytest.fixture
def test_engine():
    """Create a PostgreSQL test database for testing."""
    # Import all models to ensure they're registered with Base
    import poliloom.models  # noqa: F401
    from sqlalchemy import text

    # Use test database connection (DATABASE_URL is set by pytest-env)
    database_url = os.environ.get("DATABASE_URL")
    engine = create_engine(database_url, echo=False)

    # Setup pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Clean up after test
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_politician(test_session):
    """Create a sample politician for testing."""
    politician = Politician(name="John Doe", wikidata_id="Q123456")
    test_session.add(politician)
    test_session.commit()
    test_session.refresh(politician)
    return politician


@pytest.fixture
def sample_wikipedia_link(test_session, sample_politician):
    """Create a sample Wikipedia link for testing."""
    wikipedia_link = WikipediaLink(
        politician_id=sample_politician.id,
        url="https://en.wikipedia.org/wiki/John_Doe",
        language_code="en",
    )
    test_session.add(wikipedia_link)
    test_session.commit()
    test_session.refresh(wikipedia_link)
    return wikipedia_link


@pytest.fixture
def sample_archived_page(test_session):
    """Create a sample archived page for testing."""
    from datetime import datetime, timezone

    archived_page = ArchivedPage(
        url="https://en.wikipedia.org/wiki/Test_Page",
        content_hash="test123",
        fetch_timestamp=datetime.now(timezone.utc),
    )
    test_session.add(archived_page)
    test_session.commit()
    test_session.refresh(archived_page)
    return archived_page


@pytest.fixture
def sample_country(test_session):
    """Create a sample country for testing."""
    country = Country(name="United States", iso_code="US", wikidata_id="Q30")
    test_session.add(country)
    test_session.commit()
    test_session.refresh(country)
    return country


@pytest.fixture
def sample_position(test_session):
    """Create a sample position for testing."""
    position = Position(name="Mayor", wikidata_id="Q30185", embedding=[0.1] * 384)
    test_session.add(position)
    test_session.commit()
    test_session.refresh(position)
    return position


@pytest.fixture
def sample_mayor_of_springfield_position(test_session):
    """Create a sample 'Mayor of Springfield' position for testing."""
    position = Position(
        name="Mayor of Springfield", wikidata_id="Q30185", embedding=[0.1] * 384
    )
    test_session.add(position)
    test_session.commit()
    test_session.refresh(position)
    return position


@pytest.fixture
def sample_property(test_session, sample_politician):
    """Create a sample property for testing."""
    prop = Property(
        politician_id=sample_politician.id,
        type="BirthDate",
        value="1970-01-15",
        archived_page_id=None,
    )
    test_session.add(prop)
    test_session.commit()
    test_session.refresh(prop)
    return prop


@pytest.fixture
def sample_holds_position(test_session, sample_politician, sample_position):
    """Create a sample holds position relationship for testing."""
    holds_pos = HoldsPosition(
        politician_id=sample_politician.id,
        position_id=sample_position.id,
        start_date="2020",
        end_date="2024",
        archived_page_id=None,
    )
    test_session.add(holds_pos)
    test_session.commit()
    test_session.refresh(holds_pos)
    return holds_pos


@pytest.fixture
def sample_location(test_session):
    """Create a sample location with embedding."""
    location = Location(
        name="Springfield, Illinois",
        wikidata_id="Q28513",
        embedding=[0.2] * 384,  # Mock embedding
    )
    test_session.add(location)
    test_session.commit()
    test_session.refresh(location)
    return location


@pytest.fixture
def sample_wikipedia_content():
    """Sample Wikipedia content for testing."""
    return """
    Test Politician (born January 15, 1970 in Springfield, Illinois) is an American politician who served as Mayor of Springfield from 2020 to 2024.
    He grew up in Springfield before moving to Chicago for college.
    He previously worked as a city councilman from 2018 to 2020.
    """


@pytest.fixture
def enrichment_wikipedia_content():
    """Sample Wikipedia content from enrichment test data for testing."""
    enrichment_data = load_json_fixture("enrichment_test_data.json")
    return enrichment_data["wikipedia_content_examples"]["test_politician_article"]


@pytest.fixture
def assert_model_fields():
    """Fixture for asserting model fields."""

    def _assert_basic_model_fields(model, expected_fields):
        """Assert that model has expected basic fields."""
        assert model.id is not None
        assert model.created_at is not None
        assert model.updated_at is not None
        for field, value in expected_fields.items():
            assert getattr(model, field) == value

    return _assert_basic_model_fields


@pytest.fixture
def create_entities():
    """Fixture for creating entities and committing them to the session."""

    def _create_and_commit(session, *entities):
        """Create entities and commit them to the session."""
        session.add_all(entities)
        session.commit()
        for entity in entities:
            session.refresh(entity)
        return entities if len(entities) > 1 else entities[0]

    return _create_and_commit


@pytest.fixture
def position_with_embedding():
    """Fixture for creating a Position with embedding."""

    def _create_position_with_embedding(name, wikidata_id):
        """Create a Position with embedding."""
        from poliloom.embeddings import generate_embedding

        position = Position(name=name, wikidata_id=wikidata_id)
        position.embedding = generate_embedding(name)
        return position

    return _create_position_with_embedding


@pytest.fixture
def location_with_embedding():
    """Fixture for creating a Location with embedding."""

    def _create_location_with_embedding(name, wikidata_id):
        """Create a Location with embedding."""
        from poliloom.embeddings import generate_embedding

        location = Location(name=name, wikidata_id=wikidata_id)
        location.embedding = generate_embedding(name)
        return location

    return _create_location_with_embedding


@pytest.fixture
def similarity_searcher():
    """Fixture for performing similarity search on models with embeddings."""

    def _similarity_search(session, model_class, query_text, limit=5):
        """Perform similarity search on model with embeddings."""
        from poliloom.embeddings import generate_embedding

        query_embedding = generate_embedding(query_text)
        query = session.query(model_class).filter(model_class.embedding.isnot(None))

        return (
            query.order_by(model_class.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .all()
        )

    return _similarity_search

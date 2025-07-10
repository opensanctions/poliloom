"""Test configuration and fixtures for PoliLoom tests."""

import pytest
import json
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

    # Use test database connection (hardcoded to match docker-compose.yml)
    engine = create_engine(
        "postgresql://postgres:postgres@localhost:5433/poliloom_test", echo=False
    )

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
    politician = Politician(name="John Doe", wikidata_id="Q123456", is_deceased=False)
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
    position = Position(name="Mayor", wikidata_id="Q30185")
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
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None,
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
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None,
    )
    test_session.add(holds_pos)
    test_session.commit()
    test_session.refresh(holds_pos)
    return holds_pos


@pytest.fixture(autouse=True)
def mock_get_db_session(test_session):
    """Mock get_db_session functions globally to return test session."""
    with (
        patch("poliloom.services.enrichment_service.get_db_session") as mock_db_session,
        patch(
            "poliloom.services.enrichment_service.get_db_session_no_commit"
        ) as mock_db_session_no_commit,
        patch(
            "poliloom.services.import_service.get_db_session"
        ) as mock_import_db_session,
    ):
        # Mock both context managers to return the test session
        mock_db_session.return_value.__enter__.return_value = test_session
        mock_db_session.return_value.__exit__.return_value = None
        mock_db_session_no_commit.return_value.__enter__.return_value = test_session
        mock_db_session_no_commit.return_value.__exit__.return_value = None
        mock_import_db_session.return_value.__enter__.return_value = test_session
        mock_import_db_session.return_value.__exit__.return_value = None
        yield

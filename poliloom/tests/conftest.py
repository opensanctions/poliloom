"""Test configuration and fixtures for PoliLoom tests."""
import pytest
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from unittest.mock import patch

from poliloom.models import (
    Base, Politician, Source, Property, Position, HoldsPosition, Country
)


class MockSentenceTransformer:
    """Mock SentenceTransformer for tests."""
    def __init__(self, model_name):
        self.model_name = model_name
    
    def encode(self, text, convert_to_tensor=False):
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
    with patch('sentence_transformers.SentenceTransformer', MockSentenceTransformer):
        yield


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, 'r') as f:
        return json.load(f)


@pytest.fixture
def test_engine():
    """Create a PostgreSQL test database for testing."""
    # Import all models to ensure they're registered with Base
    import poliloom.models  # noqa: F401
    from sqlalchemy import text
    
    # Use test database connection (hardcoded to match docker-compose.yml)
    engine = create_engine(
        "postgresql://postgres:postgres@localhost:5433/poliloom_test",
        echo=False
    )
    
    # Setup pgvector extension
    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Clean up after test
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_politician(test_session):
    """Create a sample politician for testing."""
    politician = Politician(
        name="John Doe",
        wikidata_id="Q123456",
        is_deceased=False
    )
    test_session.add(politician)
    test_session.commit()
    test_session.refresh(politician)
    return politician


@pytest.fixture
def sample_source(test_session):
    """Create a sample source for testing."""
    source = Source(
        url="https://example.com/john-doe",
        extracted_at=datetime(2024, 1, 15, 10, 30, 0)
    )
    test_session.add(source)
    test_session.commit()
    test_session.refresh(source)
    return source


@pytest.fixture
def sample_country(test_session):
    """Create a sample country for testing."""
    country = Country(
        name="United States",
        iso_code="US",
        wikidata_id="Q30"
    )
    test_session.add(country)
    test_session.commit()
    test_session.refresh(country)
    return country


@pytest.fixture
def sample_position(test_session, sample_country):
    """Create a sample position for testing."""
    position = Position(
        name="Mayor",
        wikidata_id="Q30185"
    )
    position.countries.append(sample_country)
    test_session.add(position)
    test_session.commit()
    test_session.refresh(position)
    return position


@pytest.fixture
def sample_property(test_session, sample_politician, sample_source):
    """Create a sample property for testing."""
    prop = Property(
        politician_id=sample_politician.id,
        type="BirthDate",
        value="1970-01-15",
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None
    )
    prop.sources.append(sample_source)
    test_session.add(prop)
    test_session.commit()
    test_session.refresh(prop)
    return prop


@pytest.fixture
def sample_holds_position(test_session, sample_politician, sample_position, sample_source):
    """Create a sample holds position relationship for testing."""
    holds_pos = HoldsPosition(
        politician_id=sample_politician.id,
        position_id=sample_position.id,
        start_date="2020",
        end_date="2024",
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None
    )
    holds_pos.sources.append(sample_source)
    test_session.add(holds_pos)
    test_session.commit()
    test_session.refresh(holds_pos)
    return holds_pos


@pytest.fixture
def mock_wikidata_responses():
    """Mock Wikidata API responses for testing."""
    import json
    import os
    
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    
    def load_fixture(filename):
        with open(os.path.join(fixtures_dir, filename), 'r') as f:
            return json.load(f)
    
    return {
        'politician_response': load_fixture('wikidata_politician_response.json'),
        'place_response': load_fixture('wikidata_place_response.json'),
        'position_response': load_fixture('wikidata_position_response.json'),
        'country_response': load_fixture('wikidata_country_response.json'),
        'sparql_politicians_response': load_fixture('wikidata_politicians_sparql_response.json')
    }
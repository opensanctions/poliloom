"""Test configuration and fixtures for PoliLoom tests."""

import orjson
import pytest
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import text
from alembic.config import Config
from alembic import command

from poliloom.models import (
    Base,
    Position,
    Location,
)
from poliloom.services.extraction_service import generate_embedding
from poliloom.database import get_engine
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def mock_generate_embedding():
    """Mock generate_embedding to avoid loading models in tests."""

    def mock_embedding(text: str):
        """Generate a deterministic embedding based on text hash."""
        text_hash = hashlib.md5(text.encode()).digest()
        dummy_embedding = []
        for i in range(384):
            byte_val = text_hash[i % len(text_hash)]
            val = (byte_val / 127.5) - 1.0
            dummy_embedding.append(val)
        return dummy_embedding

    with patch(
        "poliloom.services.extraction_service.generate_embedding",
        side_effect=mock_embedding,
    ):
        yield


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, "rb") as f:
        return orjson.loads(f.read())


@pytest.fixture(autouse=True)
def setup_test_database():
    """Setup test database for each test using Alembic migrations."""
    # Run Alembic migrations to create tables with triggers
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    # Clean up after test - drop all tables
    engine = get_engine()
    Base.metadata.drop_all(engine)

    # Also clean up alembic version table
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()


@pytest.fixture
def sample_politician_data():
    """Return data for creating a politician."""
    return {"name": "John Doe", "wikidata_id": "Q123456"}


@pytest.fixture
def sample_wikipedia_link_data():
    """Return data for creating a Wikipedia link."""
    return {
        "url": "https://en.wikipedia.org/wiki/John_Doe",
        "language_code": "en",
    }


@pytest.fixture
def sample_archived_page_data():
    """Return data for creating an archived page."""

    return {
        "url": "https://en.wikipedia.org/wiki/Test_Page",
        "content_hash": "test123",
        "fetch_timestamp": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_country_data():
    """Return data for creating a country."""
    return {"name": "United States", "iso_code": "US", "wikidata_id": "Q30"}


@pytest.fixture
def sample_position_data():
    """Return data for creating a position."""
    return {"name": "Mayor", "wikidata_id": "Q30185", "embedding": [0.1] * 384}


@pytest.fixture
def sample_mayor_of_springfield_position_data():
    """Return data for creating a 'Mayor of Springfield' position."""
    return {
        "name": "Mayor of Springfield",
        "wikidata_id": "Q30185",
        "embedding": [0.1] * 384,
    }


@pytest.fixture
def sample_property_data():
    """Return data for creating a property."""
    return {
        "type": "BirthDate",
        "value": "1970-01-15",
        "archived_page_id": None,
    }


@pytest.fixture
def sample_holds_position_data():
    """Return data for creating a holds position relationship."""
    return {
        "start_date": "2020",
        "end_date": "2024",
        "archived_page_id": None,
    }


@pytest.fixture
def sample_location_data():
    """Return data for creating a location with embedding."""
    return {
        "name": "Springfield, Illinois",
        "wikidata_id": "Q28513",
        "embedding": [0.2] * 384,  # Mock embedding
    }


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


def assert_model_fields(model, expected_fields):
    """Assert that model has expected fields."""
    for field, value in expected_fields.items():
        assert getattr(model, field) == value


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    with Session(get_engine()) as session:
        yield session


@pytest.fixture
def position_with_embedding():
    """Fixture for creating a Position with embedding."""

    def _create_position_with_embedding(name, wikidata_id):
        """Create a Position with embedding."""
        position = Position(name=name, wikidata_id=wikidata_id)
        position.embedding = generate_embedding(name)
        return position

    return _create_position_with_embedding


@pytest.fixture
def location_with_embedding():
    """Fixture for creating a Location with embedding."""

    def _create_location_with_embedding(name, wikidata_id):
        """Create a Location with embedding."""
        location = Location(name=name, wikidata_id=wikidata_id)
        location.embedding = generate_embedding(name)
        return location

    return _create_location_with_embedding


@pytest.fixture
def similarity_searcher(db_session):
    """Fixture for performing similarity search on models with embeddings."""

    def _similarity_search(model_class, query_text, limit=5):
        """Perform similarity search on model with embeddings."""
        query_embedding = generate_embedding(query_text)
        query = db_session.query(model_class).filter(model_class.embedding.isnot(None))

        return (
            query.order_by(model_class.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .all()
        )

    return _similarity_search

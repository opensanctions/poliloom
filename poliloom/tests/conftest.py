"""Test configuration and fixtures for PoliLoom tests."""

import orjson
import pytest
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from poliloom.models import (
    ArchivedPage,
    Base,
    Country,
    Language,
    Location,
    Politician,
    Position,
    WikipediaLink,
)
from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.database import create_timestamp_triggers, create_import_tracking_triggers


@pytest.fixture
def generate_embedding():
    """Mock generate_embedding to avoid loading models in tests.

    Returns a deterministic mock function that generates embeddings based on text hash.
    Use this fixture in tests instead of importing the real generate_embedding.
    """

    def mock_embedding(text: str):
        """Generate a deterministic embedding based on text hash."""
        text_hash = hashlib.md5(text.encode()).digest()
        dummy_embedding = []
        for i in range(384):
            byte_val = text_hash[i % len(text_hash)]
            val = (byte_val / 127.5) - 1.0
            dummy_embedding.append(val)
        return dummy_embedding

    return mock_embedding


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, "rb") as f:
        return orjson.loads(f.read())


@pytest.fixture(autouse=True)
def setup_test_database_fixture():
    """Setup test database for each test using SQLAlchemy directly."""

    engine = get_engine()

    # Create all tables using SQLAlchemy
    Base.metadata.create_all(engine)

    # Setup all required triggers AFTER creating tables
    create_timestamp_triggers(engine)
    create_import_tracking_triggers(engine)

    yield

    # Clean up after test - drop all tables
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_politician_data():
    """Return data for creating a politician."""
    return {"name": "Test Politician", "wikidata_id": "Q123456"}


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
def similarity_searcher(db_session, generate_embedding):
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


# Entity fixtures - created and committed to database
@pytest.fixture
def sample_politician(db_session, sample_politician_data):
    """Return a created and committed politician entity."""
    politician = Politician.create_with_entity(
        db_session,
        sample_politician_data["wikidata_id"],
        sample_politician_data["name"],
    )
    db_session.commit()
    db_session.refresh(politician)
    return politician


@pytest.fixture
def sample_position(db_session):
    """Return a created and committed position entity with embedding."""
    position = Position.create_with_entity(db_session, "Q30185", "Test Position")
    # Set embedding for tests that require it
    position.embedding = [0.1] * 384
    db_session.commit()
    db_session.refresh(position)
    return position


@pytest.fixture
def sample_location(db_session):
    """Return a created and committed location entity with labels for fuzzy search."""
    location = Location.create_with_entity(
        db_session,
        "Q28513",
        "Test Location",
        labels=["Test Location", "Test Loc"],
    )
    db_session.commit()
    db_session.refresh(location)
    return location


@pytest.fixture
def sample_country(db_session):
    """Return a created and committed country entity."""
    country = Country.create_with_entity(db_session, "Q30", "United States")
    country.iso_code = "US"
    db_session.commit()
    db_session.refresh(country)
    return country


@pytest.fixture
def sample_language(db_session):
    """Return a created and committed language entity."""
    language = Language.create_with_entity(db_session, "Q1860", "English")
    language.iso1_code = "en"
    language.iso3_code = "eng"
    db_session.commit()
    db_session.refresh(language)
    return language


@pytest.fixture
def sample_archived_page(db_session):
    """Return a created and committed archived page entity."""
    archived_page = ArchivedPage(
        url="https://en.wikipedia.org/wiki/Test_Page",
        content_hash="test123",
        fetch_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(archived_page)
    db_session.commit()
    db_session.refresh(archived_page)
    return archived_page


@pytest.fixture
def sample_wikipedia_link(db_session, sample_politician):
    """Return a created and committed Wikipedia link entity."""
    wikipedia_link = WikipediaLink(
        politician_id=sample_politician.id,
        url="https://en.wikipedia.org/wiki/Test_Politician",
        iso_code="en",
    )
    db_session.add(wikipedia_link)
    db_session.commit()
    db_session.refresh(wikipedia_link)
    return wikipedia_link

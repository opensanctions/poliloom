"""Test configuration and fixtures for PoliLoom tests."""

import orjson
import pytest
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from poliloom.models import (
    ArchivedPage,
    Base,
    Country,
    Language,
    Location,
    Politician,
    Position,
    Property,
    PropertyType,
    WikipediaLink,
)
from poliloom.embeddings import generate_embedding
from poliloom.database import get_engine, setup_test_database
from poliloom.wikidata_date import WikidataDate
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
        "poliloom.embeddings.generate_embedding",
        side_effect=mock_embedding,
    ):
        yield


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

    # Setup all required triggers (timestamp + import tracking)
    setup_test_database(engine)

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
    """Return a created and committed location entity."""
    location = Location.create_with_entity(db_session, "Q28513", "Test Location")
    # Set the embedding for tests
    location.embedding = [0.2] * 384
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


@pytest.fixture
def sample_position_property(db_session, sample_politician, sample_position):
    """Return a created and committed Property entity for a position with qualifiers_json."""
    # Create qualifiers_json with start and end dates using WikidataDate
    start_date = WikidataDate.from_date_string("2020-01")
    end_date = WikidataDate.from_date_string("2023-12-31")
    qualifiers_json = {
        "P580": [start_date.to_wikidata_qualifier()],
        "P582": [end_date.to_wikidata_qualifier()],
    }

    position_property = Property(
        politician_id=sample_politician.id,
        type=PropertyType.POSITION,
        entity_id=sample_position.wikidata_id,
        qualifiers_json=qualifiers_json,
    )
    db_session.add(position_property)
    db_session.commit()
    db_session.refresh(position_property)
    return position_property

"""Test configuration and fixtures for PoliLoom tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from poliloom.database import get_db
from poliloom.models import Base, Politician, Source, Property, Position, HoldsPosition, Country


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


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
        country_id=sample_country.id,
        wikidata_id="Q30185"
    )
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
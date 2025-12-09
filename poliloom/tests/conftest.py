"""Test configuration and fixtures for PoliLoom tests.

Minimal fixtures - only database session and external service mocks.
Tests should create their own test data directly using model constructors.
"""

import pytest
import hashlib
import uuid
from unittest.mock import AsyncMock, Mock as SyncMock, patch

from poliloom.models import Base
from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.database import create_timestamp_triggers, create_import_tracking_triggers


@pytest.fixture(autouse=True)
def mock_embeddings_batch():
    """Mock generate_embeddings_batch to avoid loading transformer models in tests.

    Applied automatically to all tests.
    """

    def mock_batch(texts):
        """Generate deterministic embeddings for a batch of texts."""
        embeddings = []
        for text in texts:
            text_hash = hashlib.md5(text.encode()).digest()
            dummy_embedding = []
            for i in range(384):
                byte_val = text_hash[i % len(text_hash)]
                val = (byte_val / 127.5) - 1.0
                dummy_embedding.append(val)
            embeddings.append(dummy_embedding)
        return embeddings

    # Patch both the source module and where it's imported
    with (
        patch("poliloom.embeddings.generate_embeddings_batch", side_effect=mock_batch),
        patch("poliloom.enrichment.generate_embeddings_batch", side_effect=mock_batch),
    ):
        yield


@pytest.fixture(scope="session")
def setup_test_database():
    """Setup test database once for the entire test session."""
    engine = get_engine()

    # Create all tables once at the start of the test session
    Base.metadata.create_all(engine)

    # Create triggers once for all tests
    create_timestamp_triggers(engine)
    create_import_tracking_triggers(engine)

    yield engine

    # Clean up after all tests complete - drop all tables
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(setup_test_database):
    """Provide a database session for tests with transaction rollback.

    Each test runs in a transaction that is rolled back after the test completes.
    This ensures test isolation without needing to recreate the database schema.
    """
    engine = setup_test_database

    # Create a connection and begin a transaction
    connection = engine.connect()
    connection.begin()

    # Create a session bound to the connection
    session = Session(bind=connection)

    yield session

    # Clean up - closing the connection automatically rolls back any uncommitted transaction
    session.close()
    connection.close()


# =============================================================================
# API TEST FIXTURES
# =============================================================================


@pytest.fixture
def client(db_session):
    """Create a FastAPI test client with overridden database session.

    Uses dependency_overrides to inject the transaction-based test session
    into all API endpoints, ensuring test isolation.
    """
    from fastapi.testclient import TestClient
    from poliloom.api import app
    from poliloom.database import get_db_session

    def override_get_db():
        """Override database session to use the test transaction."""
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth():
    """Mock authentication for API tests.

    Returns authorization headers dict and mocks the OAuth handler
    to return a user with a JWT token.
    """
    from poliloom.api.auth import User

    with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
        mock_user = User(user_id=12345, jwt_token="mock_jwt_token_for_testing")
        mock_oauth_handler = SyncMock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        yield {"Authorization": "Bearer valid_jwt_token"}


@pytest.fixture(autouse=True)
def mock_wikidata_api():
    """Mock Wikidata API calls for entity and statement creation.

    This fixture automatically mocks all Wikidata API interactions
    to avoid real API calls during testing. Applied to all tests automatically.
    """

    async def mock_create_entity_fn(label, *args, **kwargs):
        label_hash = hashlib.md5(label.encode()).hexdigest()
        qid_number = int(label_hash[:8], 16) % 100000000
        return f"Q{qid_number}"

    async def mock_create_statement_fn(entity_id, *args, **kwargs):
        statement_uuid = str(uuid.uuid4())
        return f"{entity_id}${statement_uuid}"

    async def mock_deprecate_statement_fn(entity_id, statement_id, *args, **kwargs):
        return None

    with (
        patch(
            "poliloom.api.politicians.create_entity", side_effect=mock_create_entity_fn
        ) as mock_create_entity,
        patch(
            "poliloom.api.politicians.create_statement",
            side_effect=mock_create_statement_fn,
        ) as mock_create_statement,
        patch(
            "poliloom.wikidata_statement.create_statement",
            side_effect=mock_create_statement_fn,
        ),
        patch(
            "poliloom.wikidata_statement.deprecate_statement",
            side_effect=mock_deprecate_statement_fn,
        ) as mock_deprecate_statement,
        patch(
            "poliloom.wikidata_statement.create_entity",
            side_effect=mock_create_entity_fn,
        ),
    ):
        yield {
            "create_entity": mock_create_entity,
            "create_statement": mock_create_statement,
            "deprecate_statement": mock_deprecate_statement,
        }

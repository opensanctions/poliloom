"""Test configuration and fixtures for PoliLoom tests."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from unittest.mock import Mock as SyncMock

import orjson
import pytest
from sqlalchemy.orm import Session

from poliloom.database import (
    create_import_tracking_triggers,
    create_timestamp_triggers,
    get_engine,
)
from poliloom.models import (
    Base,
    Country,
    Language,
    Location,
    Politician,
    Position,
    Source,
    SourceLanguage,
    Statement,
    WikidataEntity,
    WikipediaLink,
)


def make_terms(name: str | None = None, aliases: list[str] | None = None) -> dict:
    """Build term maps shaped like the importer's get_terms() output."""
    return {
        "labels": {"en": name} if name else {},
        "descriptions": {},
        "aliases": {"en": aliases} if aliases else {},
    }


@pytest.fixture(autouse=True)
def mock_find_similar(db_session):
    """Mock find_similar on all searchable models to use term-based search.

    This avoids needing Meilisearch in tests.
    Applied automatically to all tests.
    """

    def make_mock_find_similar(model_class):
        """Create a mock find_similar that searches label and alias values."""

        @classmethod
        def mock_find_similar(cls, query, limit=100):
            query_lower = query.lower()
            entities = (
                db_session.query(model_class)
                .join(
                    WikidataEntity,
                    model_class.wikidata_id == WikidataEntity.wikidata_id,
                )
                .all()
            )
            matches = []
            for entity in entities:
                terms = entity.wikidata_entity
                values = list(terms.labels.values())
                for language_aliases in terms.aliases.values():
                    values.extend(language_aliases)
                if any(query_lower in value.lower() for value in values):
                    matches.append(entity.wikidata_id)
            return matches[:limit]

        return mock_find_similar

    # Patch find_similar on all searchable models
    with (
        patch.object(Location, "find_similar", make_mock_find_similar(Location)),
        patch.object(Country, "find_similar", make_mock_find_similar(Country)),
        patch.object(Language, "find_similar", make_mock_find_similar(Language)),
        patch.object(Position, "find_similar", make_mock_find_similar(Position)),
        patch.object(Politician, "find_similar", make_mock_find_similar(Politician)),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_search():
    """Mock poliloom.search functions to avoid connecting to Meilisearch in tests.

    Applied automatically to all tests. Tests can assert on the mocks, e.g.
    mock_search.delete_documents.assert_called_once_with(["Q1"]).
    """
    with (
        patch("poliloom.search.index_documents") as index_documents,
        patch("poliloom.search.delete_documents") as delete_documents,
        patch("poliloom.search.search") as search_,
    ):
        index_documents.return_value = 1
        delete_documents.side_effect = lambda ids, **kwargs: len(ids)
        search_.return_value = []
        yield SimpleNamespace(
            index_documents=index_documents,
            delete_documents=delete_documents,
            search=search_,
        )


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, "rb") as f:
        return orjson.loads(f.read())


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


def assert_model_fields(model, expected_fields):
    """Assert that model has expected fields."""
    for field, value in expected_fields.items():
        assert getattr(model, field) == value


@pytest.fixture
def db_session(setup_test_database):
    """Provide a database session for tests with transaction rollback.

    Each test runs in a transaction that is rolled back after the test completes.
    This ensures test isolation without needing to recreate the database schema.
    """
    engine = setup_test_database

    # Create a connection and begin a transaction
    connection = engine.connect()
    transaction = connection.begin()

    # Create a session bound to the connection
    session = Session(bind=connection)

    yield session

    # Rollback the transaction to clean up any changes made during the test
    # Note: Always rollback to catch tests that trigger database-level errors
    session.close()
    transaction.rollback()
    connection.close()


# Entity fixtures - created and committed to database
@pytest.fixture
def sample_politician(db_session):
    """Return a created politician entity."""
    politician = Politician.create_with_entity(
        db_session,
        "Q123456",
        make_terms("Test Politician", aliases=["John Doe", "Test Person"]),
    )
    db_session.flush()
    return politician


@pytest.fixture
def sample_position(db_session):
    """Return a created position entity."""
    position = Position.create_with_entity(
        db_session, "Q30185", make_terms("Test Position")
    )
    db_session.flush()
    return position


@pytest.fixture
def sample_location(db_session):
    """Return a created location entity with aliases for fuzzy search."""
    location = Location.create_with_entity(
        db_session,
        "Q28513",
        make_terms("Test Location", aliases=["Test Loc"]),
    )
    db_session.flush()
    return location


@pytest.fixture
def sample_country(db_session):
    """Return a created country entity."""
    country = Country.create_with_entity(db_session, "Q30", make_terms("United States"))
    country.iso_code = "US"
    db_session.flush()
    return country


@pytest.fixture
def sample_germany_country(db_session):
    """Return a created Germany country entity."""
    country = Country.create_with_entity(db_session, "Q183", make_terms("Germany"))
    country.iso_code = "DE"
    db_session.flush()
    return country


@pytest.fixture
def sample_france_country(db_session):
    """Return a created France country entity."""
    country = Country.create_with_entity(db_session, "Q142", make_terms("France"))
    country.iso_code = "FR"
    db_session.flush()
    return country


@pytest.fixture
def sample_argentina_country(db_session):
    """Return a created Argentina country entity."""
    country = Country.create_with_entity(db_session, "Q414", make_terms("Argentina"))
    country.iso_code = "AR"
    db_session.flush()
    return country


@pytest.fixture
def sample_spain_country(db_session):
    """Return a created Spain country entity."""
    country = Country.create_with_entity(db_session, "Q29", make_terms("Spain"))
    country.iso_code = "ES"
    db_session.flush()
    return country


@pytest.fixture
def sample_language(db_session):
    """Return a created language entity."""
    language = Language.create_with_entity(db_session, "Q1860", make_terms("English"))
    language.iso_639_1 = "en"
    language.iso_639_2 = "eng"
    db_session.flush()
    return language


@pytest.fixture
def sample_german_language(db_session):
    """Return a created German language entity."""
    language = Language.create_with_entity(db_session, "Q188", make_terms("German"))
    language.iso_639_1 = "de"
    language.iso_639_2 = "deu"
    db_session.flush()
    return language


@pytest.fixture
def sample_french_language(db_session):
    """Return a created French language entity."""
    language = Language.create_with_entity(db_session, "Q150", make_terms("French"))
    language.iso_639_1 = "fr"
    language.iso_639_2 = "fra"
    db_session.flush()
    return language


@pytest.fixture
def sample_source(db_session):
    """Return a created source entity."""
    source = Source(
        url="https://en.wikipedia.org/wiki/Test_Page",
        url_hash="test123",
        fetch_timestamp=datetime.now(UTC),
    )
    db_session.add(source)
    db_session.flush()
    return source


@pytest.fixture
def create_source(db_session):
    """Factory fixture to create sources with language links.

    Returns a function that creates a Source with optional language associations.
    """

    def _create_source(url, url_hash=None, languages=None):
        """Create a source with optional language links.

        Args:
            url: Page URL
            url_hash: Optional content hash (auto-generated if not provided)
            languages: Optional list of Language entities to link to this source

        Returns:
            Created Source instance
        """
        source = Source(
            url=url,
            url_hash=url_hash,
            fetch_timestamp=datetime.now(UTC),
        )
        db_session.add(source)
        db_session.flush()

        # Create language links if provided
        if languages:
            for language in languages:
                lang_link = SourceLanguage(
                    source_id=source.id, language_id=language.wikidata_id
                )
                db_session.add(lang_link)
            db_session.flush()

        return source

    return _create_source


@pytest.fixture
def sample_wikipedia_project(db_session, sample_language):
    """Return a created English Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import RelationType, WikidataRelation, WikipediaProject

    wp = WikipediaProject.create_with_entity(
        db_session, "Q328", make_terms("English Wikipedia")
    )
    wp.official_website = "https://en.wikipedia.org"

    # Create LANGUAGE_OF_WORK relation
    relation = WikidataRelation(
        parent_entity_id=sample_language.wikidata_id,
        child_entity_id=wp.wikidata_id,
        relation_type=RelationType.LANGUAGE_OF_WORK,
        statement_id="test_en_wp_lang",
    )
    db_session.add(relation)
    db_session.flush()
    return wp


@pytest.fixture
def sample_german_wikipedia_project(db_session, sample_german_language):
    """Return a created German Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import RelationType, WikidataRelation, WikipediaProject

    wp = WikipediaProject.create_with_entity(
        db_session, "Q48183", make_terms("German Wikipedia")
    )
    wp.official_website = "https://de.wikipedia.org"

    # Create LANGUAGE_OF_WORK relation
    relation = WikidataRelation(
        parent_entity_id=sample_german_language.wikidata_id,
        child_entity_id=wp.wikidata_id,
        relation_type=RelationType.LANGUAGE_OF_WORK,
        statement_id="test_de_wp_lang",
    )
    db_session.add(relation)
    db_session.flush()
    return wp


@pytest.fixture
def sample_french_wikipedia_project(db_session, sample_french_language):
    """Return a created French Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import RelationType, WikidataRelation, WikipediaProject

    wp = WikipediaProject.create_with_entity(
        db_session, "Q8447", make_terms("French Wikipedia")
    )
    wp.official_website = "https://fr.wikipedia.org"

    # Create LANGUAGE_OF_WORK relation
    relation = WikidataRelation(
        parent_entity_id=sample_french_language.wikidata_id,
        child_entity_id=wp.wikidata_id,
        relation_type=RelationType.LANGUAGE_OF_WORK,
        statement_id="test_fr_wp_lang",
    )
    db_session.add(relation)
    db_session.flush()
    return wp


@pytest.fixture
def sample_spanish_language(db_session):
    """Return a created Spanish language entity."""
    language = Language.create_with_entity(db_session, "Q1321", make_terms("Spanish"))
    language.iso_639_1 = "es"
    language.iso_639_2 = "spa"
    db_session.flush()
    return language


@pytest.fixture
def sample_spanish_wikipedia_project(db_session, sample_spanish_language):
    """Return a created Spanish Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import RelationType, WikidataRelation, WikipediaProject

    wp = WikipediaProject.create_with_entity(
        db_session, "Q8449", make_terms("Spanish Wikipedia")
    )
    wp.official_website = "https://es.wikipedia.org"

    # Create LANGUAGE_OF_WORK relation
    relation = WikidataRelation(
        parent_entity_id=sample_spanish_language.wikidata_id,
        child_entity_id=wp.wikidata_id,
        relation_type=RelationType.LANGUAGE_OF_WORK,
        statement_id="test_es_wp_lang",
    )
    db_session.add(relation)
    db_session.flush()
    return wp


@pytest.fixture
def create_wikipedia_link(db_session):
    """Factory fixture to create Wikipedia links easily.

    Returns a function that creates a WikipediaLink given a politician and Wikipedia project.
    """

    def _create_link(politician, wikipedia_project, article_title=None):
        """Create a Wikipedia link for a politician.

        Args:
            politician: Politician instance
            wikipedia_project: WikipediaProject instance
            article_title: Optional article title (defaults to politician name with underscores)
        """
        if article_title is None:
            article_title = (politician.wikidata_entity.resolved_label or "").replace(
                " ", "_"
            )

        # Extract domain from official_website (e.g., "https://en.wikipedia.org")
        domain = wikipedia_project.official_website
        url = f"{domain}/wiki/{article_title}"

        link = WikipediaLink(
            politician_id=politician.id,
            url=url,
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(link)
        return link

    return _create_link


@pytest.fixture
def sample_wikipedia_link(db_session, sample_politician, sample_wikipedia_project):
    """Return a created Wikipedia link entity."""
    wikipedia_link = WikipediaLink(
        politician_id=sample_politician.id,
        url="https://en.wikipedia.org/wiki/Test_Politician",
        wikipedia_project_id=sample_wikipedia_project.wikidata_id,
    )
    db_session.add(wikipedia_link)
    db_session.flush()
    return wikipedia_link


@pytest.fixture
def create_citizenship(db_session):
    """Factory to create live P27 citizenship statements."""

    def _create_citizenship(politician, country):
        """Create a citizenship statement for a politician.

        Args:
            politician: Politician instance
            country: Country instance

        Returns:
            Created Statement instance
        """
        statement = Statement(
            politician_id=politician.id,
            document={
                "id": f"{politician.wikidata_id}$p27-{uuid.uuid4()}",
                "rank": "normal",
                "property": {"id": "P27", "data_type": "wikibase-item"},
                "value": {"type": "value", "content": country.wikidata_id},
            },
        )
        db_session.add(statement)
        db_session.flush()
        return statement

    return _create_citizenship


# API Test Fixtures


@pytest.fixture
def client(db_session):
    """Create a FastAPI test client with overridden database session.

    Uses dependency_overrides to inject the transaction-based test session
    into all API endpoints, ensuring test isolation.

    Note: find_similar is mocked globally via mock_find_similar fixture.
    """
    from fastapi.testclient import TestClient

    from poliloom.api import app
    from poliloom.database import get_db_session

    def override_get_db():
        """Override database session to use the test transaction."""
        yield db_session

    # Override the dependencies
    app.dependency_overrides[get_db_session] = override_get_db

    yield TestClient(app)

    # Clean up the override after the test
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

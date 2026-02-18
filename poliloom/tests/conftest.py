"""Test configuration and fixtures for PoliLoom tests."""

import hashlib
import orjson
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock as SyncMock, patch

from poliloom.models import (
    ArchivedPage,
    ArchivedPageLanguage,
    Base,
    Country,
    Language,
    Location,
    Politician,
    Position,
    PropertyReference,
    WikipediaLink,
)
from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.database import create_timestamp_triggers, create_import_tracking_triggers


@pytest.fixture(autouse=True)
def mock_find_similar(db_session):
    """Mock find_similar on all searchable models to use label-based search.

    This avoids needing Meilisearch in tests.
    Applied automatically to all tests.
    """
    from poliloom.models import WikidataEntityLabel

    def make_mock_find_similar(model_class):
        """Create a mock find_similar that searches by labels."""

        @classmethod
        def mock_find_similar(cls, query, search_service, limit=100):
            query_lower = query.lower()
            results = (
                db_session.query(WikidataEntityLabel.entity_id)
                .join(
                    model_class,
                    WikidataEntityLabel.entity_id == model_class.wikidata_id,
                )
                .filter(WikidataEntityLabel.label.ilike(f"%{query_lower}%"))
                .distinct()
                .limit(limit)
                .all()
            )
            return [r[0] for r in results]

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
def mock_search_service_globally():
    """Mock SearchService globally to avoid connecting to Meilisearch in tests.

    Applied automatically to all tests.
    """
    with patch("poliloom.search.SearchService") as mock_class:
        mock_instance = SyncMock()
        mock_instance.index_documents.return_value = 1
        mock_instance.delete_documents.return_value = 0
        mock_instance.search.return_value = []
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_search_service():
    """Mock SearchService for importer tests.

    Returns a mock that tracks index_documents calls but doesn't connect to Meilisearch.
    """
    service = SyncMock()
    service.index_documents.return_value = 1  # Returns task_uid
    service.wait_for_tasks.return_value = None
    return service


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
        "Test Politician",
        labels=["Test Politician", "John Doe", "Test Person"],
    )
    db_session.flush()
    return politician


@pytest.fixture
def sample_position(db_session):
    """Return a created position entity."""
    position = Position.create_with_entity(db_session, "Q30185", "Test Position")
    db_session.flush()
    return position


@pytest.fixture
def sample_location(db_session):
    """Return a created location entity with labels for fuzzy search."""
    location = Location.create_with_entity(
        db_session,
        "Q28513",
        "Test Location",
        labels=["Test Location", "Test Loc"],
    )
    db_session.flush()
    return location


@pytest.fixture
def sample_country(db_session):
    """Return a created country entity."""
    country = Country.create_with_entity(db_session, "Q30", "United States")
    country.iso_code = "US"
    db_session.flush()
    return country


@pytest.fixture
def sample_germany_country(db_session):
    """Return a created Germany country entity."""
    country = Country.create_with_entity(db_session, "Q183", "Germany")
    country.iso_code = "DE"
    db_session.flush()
    return country


@pytest.fixture
def sample_france_country(db_session):
    """Return a created France country entity."""
    country = Country.create_with_entity(db_session, "Q142", "France")
    country.iso_code = "FR"
    db_session.flush()
    return country


@pytest.fixture
def sample_argentina_country(db_session):
    """Return a created Argentina country entity."""
    country = Country.create_with_entity(db_session, "Q414", "Argentina")
    country.iso_code = "AR"
    db_session.flush()
    return country


@pytest.fixture
def sample_spain_country(db_session):
    """Return a created Spain country entity."""
    country = Country.create_with_entity(db_session, "Q29", "Spain")
    country.iso_code = "ES"
    db_session.flush()
    return country


@pytest.fixture
def sample_language(db_session):
    """Return a created language entity."""
    language = Language.create_with_entity(db_session, "Q1860", "English")
    language.iso_639_1 = "en"
    language.iso_639_2 = "eng"
    db_session.flush()
    return language


@pytest.fixture
def sample_german_language(db_session):
    """Return a created German language entity."""
    language = Language.create_with_entity(db_session, "Q188", "German")
    language.iso_639_1 = "de"
    language.iso_639_2 = "deu"
    db_session.flush()
    return language


@pytest.fixture
def sample_french_language(db_session):
    """Return a created French language entity."""
    language = Language.create_with_entity(db_session, "Q150", "French")
    language.iso_639_1 = "fr"
    language.iso_639_2 = "fra"
    db_session.flush()
    return language


@pytest.fixture
def sample_archived_page(db_session):
    """Return a created archived page entity."""
    archived_page = ArchivedPage(
        url="https://en.wikipedia.org/wiki/Test_Page",
        content_hash="test123",
        fetch_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(archived_page)
    db_session.flush()
    return archived_page


@pytest.fixture
def create_archived_page(db_session):
    """Factory fixture to create archived pages with language links.

    Returns a function that creates an ArchivedPage with optional language associations.
    """

    def _create_archived_page(url, content_hash=None, languages=None):
        """Create an archived page with optional language links.

        Args:
            url: Page URL
            content_hash: Optional content hash (auto-generated if not provided)
            languages: Optional list of Language entities to link to this page

        Returns:
            Created ArchivedPage instance
        """
        archived_page = ArchivedPage(
            url=url,
            content_hash=content_hash,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        # Create language links if provided
        if languages:
            for language in languages:
                lang_link = ArchivedPageLanguage(
                    archived_page_id=archived_page.id, language_id=language.wikidata_id
                )
                db_session.add(lang_link)
            db_session.flush()

        return archived_page

    return _create_archived_page


@pytest.fixture
def sample_wikipedia_project(db_session, sample_language):
    """Return a created English Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import WikipediaProject, WikidataRelation, RelationType

    wp = WikipediaProject.create_with_entity(db_session, "Q328", "English Wikipedia")
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
    from poliloom.models import WikipediaProject, WikidataRelation, RelationType

    wp = WikipediaProject.create_with_entity(db_session, "Q48183", "German Wikipedia")
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
    from poliloom.models import WikipediaProject, WikidataRelation, RelationType

    wp = WikipediaProject.create_with_entity(db_session, "Q8447", "French Wikipedia")
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
    language = Language.create_with_entity(db_session, "Q1321", "Spanish")
    language.iso_639_1 = "es"
    language.iso_639_2 = "spa"
    db_session.flush()
    return language


@pytest.fixture
def sample_spanish_wikipedia_project(db_session, sample_spanish_language):
    """Return a created Spanish Wikipedia project entity with LANGUAGE_OF_WORK relation."""
    from poliloom.models import WikipediaProject, WikidataRelation, RelationType

    wp = WikipediaProject.create_with_entity(db_session, "Q8449", "Spanish Wikipedia")
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
            article_title = politician.name.replace(" ", "_")

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
    """Factory fixture to create citizenship properties easily.

    Returns a function that creates a citizenship Property given a politician and country.
    """
    from poliloom.models import Property, PropertyType

    def _create_citizenship(politician, country, archived_page=None):
        """Create a citizenship property for a politician.

        Args:
            politician: Politician instance
            country: Country instance
            archived_page: Optional ArchivedPage instance (creates a PropertyReference)

        Returns:
            Created Property instance
        """
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )
        db_session.add(prop)
        db_session.flush()
        if archived_page:
            ref = PropertyReference(
                property_id=prop.id,
                archived_page_id=archived_page.id,
            )
            db_session.add(ref)
        return prop

    return _create_citizenship


@pytest.fixture
def create_birth_date(db_session):
    """Factory fixture to create birth date properties easily.

    Returns a function that creates a BIRTH_DATE Property given a politician and value.
    """
    from poliloom.models import Property, PropertyType

    def _create_birth_date(
        politician,
        value="1980-01-01",
        archived_page=None,
        statement_id=None,
        supporting_quotes=None,
    ):
        """Create a birth date property for a politician.

        Args:
            politician: Politician instance
            value: Date string (default: "1980-01-01")
            archived_page: Optional ArchivedPage instance (creates a PropertyReference)
            statement_id: Optional statement ID (makes it "from Wikidata")
            supporting_quotes: Optional list of supporting quotes

        Returns:
            Created Property instance
        """
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value=value,
            value_precision=11,
            statement_id=statement_id,
        )
        db_session.add(prop)
        db_session.flush()
        if archived_page:
            ref = PropertyReference(
                property_id=prop.id,
                archived_page_id=archived_page.id,
                supporting_quotes=supporting_quotes,
            )
            db_session.add(ref)
        return prop

    return _create_birth_date


@pytest.fixture
def create_death_date(db_session):
    """Factory fixture to create death date properties easily.

    Returns a function that creates a DEATH_DATE Property given a politician and value.
    """
    from poliloom.models import Property, PropertyType

    def _create_death_date(
        politician,
        value="2020-01-01",
        archived_page=None,
        statement_id=None,
        supporting_quotes=None,
    ):
        """Create a death date property for a politician.

        Args:
            politician: Politician instance
            value: Date string (default: "2020-01-01")
            archived_page: Optional ArchivedPage instance (creates a PropertyReference)
            statement_id: Optional statement ID (makes it "from Wikidata")
            supporting_quotes: Optional list of supporting quotes

        Returns:
            Created Property instance
        """
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value=value,
            value_precision=11,
            statement_id=statement_id,
        )
        db_session.add(prop)
        db_session.flush()
        if archived_page:
            ref = PropertyReference(
                property_id=prop.id,
                archived_page_id=archived_page.id,
                supporting_quotes=supporting_quotes,
            )
            db_session.add(ref)
        return prop

    return _create_death_date


@pytest.fixture
def create_position(db_session):
    """Factory fixture to create position properties easily.

    Returns a function that creates a POSITION Property given a politician and position.
    """
    from poliloom.models import Property, PropertyType

    def _create_position(
        politician,
        position,
        archived_page=None,
        qualifiers_json=None,
        statement_id=None,
        supporting_quotes=None,
    ):
        """Create a position property for a politician.

        Args:
            politician: Politician instance
            position: Position instance
            archived_page: Optional ArchivedPage instance (creates a PropertyReference)
            qualifiers_json: Optional qualifiers dict (e.g., P580/P582 for dates)
            statement_id: Optional statement ID (makes it "from Wikidata")
            supporting_quotes: Optional list of supporting quotes

        Returns:
            Created Property instance
        """
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json=qualifiers_json,
            statement_id=statement_id,
        )
        db_session.add(prop)
        db_session.flush()
        if archived_page:
            ref = PropertyReference(
                property_id=prop.id,
                archived_page_id=archived_page.id,
                supporting_quotes=supporting_quotes,
            )
            db_session.add(ref)
        return prop

    return _create_position


@pytest.fixture
def create_birthplace(db_session):
    """Factory fixture to create birthplace properties easily.

    Returns a function that creates a BIRTHPLACE Property given a politician and location.
    """
    from poliloom.models import Property, PropertyType

    def _create_birthplace(
        politician,
        location,
        archived_page=None,
        statement_id=None,
        supporting_quotes=None,
    ):
        """Create a birthplace property for a politician.

        Args:
            politician: Politician instance
            location: Location instance
            archived_page: Optional ArchivedPage instance (creates a PropertyReference)
            statement_id: Optional statement ID (makes it "from Wikidata")
            supporting_quotes: Optional list of supporting quotes

        Returns:
            Created Property instance
        """
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            statement_id=statement_id,
        )
        db_session.add(prop)
        db_session.flush()
        if archived_page:
            ref = PropertyReference(
                property_id=prop.id,
                archived_page_id=archived_page.id,
                supporting_quotes=supporting_quotes,
            )
            db_session.add(ref)
        return prop

    return _create_birthplace


@pytest.fixture
def politician_with_unevaluated_data(
    db_session, sample_politician, sample_position, sample_location
):
    """Create a politician with various types of unevaluated extracted data.

    This fixture creates a politician with:
    - Extracted (unevaluated) properties: birth date, position, birthplace
    - Wikidata properties: death date, position, birthplace

    Returns:
        Tuple of (politician, list of extracted properties)
    """
    from poliloom.models import Property, PropertyType
    from poliloom.wikidata_date import WikidataDate

    archived_page = ArchivedPage(
        url="https://example.com/test",
        content_hash="test123",
    )
    db_session.add(archived_page)
    db_session.flush()

    politician = sample_politician
    position = sample_position
    location = sample_location

    # Add extracted (unevaluated) data
    extracted_birth = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1970-01-15",
        value_precision=11,
    )

    extracted_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
        },
    )

    extracted_birthplace = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTHPLACE,
        entity_id=location.wikidata_id,
    )

    # Add Wikidata (non-extracted) data
    wikidata_death = Property(
        politician_id=politician.id,
        type=PropertyType.DEATH_DATE,
        value="2024-01-01",
        value_precision=11,
    )

    wikidata_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2018").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
        },
    )

    wikidata_birthplace = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTHPLACE,
        entity_id=location.wikidata_id,
    )

    extracted_properties = [extracted_birth, extracted_position, extracted_birthplace]
    wikidata_properties = [wikidata_death, wikidata_position, wikidata_birthplace]

    db_session.add_all(extracted_properties + wikidata_properties)
    db_session.flush()

    # Create PropertyReferences for extracted properties
    refs = [
        PropertyReference(
            property_id=extracted_birth.id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 15, 1970"],
        ),
        PropertyReference(
            property_id=extracted_position.id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Served as Mayor from 2020 to 2024"],
        ),
        PropertyReference(
            property_id=extracted_birthplace.id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born in Springfield"],
        ),
    ]
    db_session.add_all(refs)
    db_session.flush()

    return politician, extracted_properties


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


@pytest.fixture(autouse=True)
def mock_wikidata_api():
    """Mock Wikidata API calls for entity and statement creation.

    This fixture automatically mocks all Wikidata API interactions
    to avoid real API calls during testing. Applied to all tests automatically.

    Mocks functions in both:
    - poliloom.api.politicians (used by create/add politician endpoints)
    - poliloom.wikidata_statement (used by push_evaluation)
    """
    import uuid

    async def mock_create_entity_fn(label, *args, **kwargs):
        # Hash the label to get a deterministic but unique QID
        label_hash = hashlib.md5(label.encode()).hexdigest()
        qid_number = int(label_hash[:8], 16) % 100000000  # Keep it reasonably sized
        return f"Q{qid_number}"

    async def mock_create_statement_fn(entity_id, *args, **kwargs):
        # Generate random UUID for statement ID
        statement_uuid = str(uuid.uuid4())
        return f"{entity_id}${statement_uuid}"

    async def mock_deprecate_statement_fn(entity_id, statement_id, *args, **kwargs):
        # Deprecate doesn't return anything, just succeeds
        return None

    with (
        # Mock imports in politicians module
        patch(
            "poliloom.api.politicians.create_entity", side_effect=mock_create_entity_fn
        ) as mock_create_entity,
        patch(
            "poliloom.api.politicians.create_statement",
            side_effect=mock_create_statement_fn,
        ) as mock_create_statement,
        # Mock functions in wikidata_statement module (used by push_evaluation)
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

"""Tests for the entities API endpoints (languages, countries, positions, locations)."""

from datetime import datetime, timezone

from poliloom.models import (
    Country,
    Language,
    Location,
    Politician,
    Position,
    Property,
    PropertyType,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)


class TestGetLanguages:
    """Test the GET /languages endpoint."""

    def test_languages_with_wikipedia_sources(self, client, mock_auth, db_session):
        """Languages should count Wikipedia links through WikipediaProject relations."""
        # Create languages
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        german = Language.create_with_entity(db_session, "Q188", "German")
        german.iso_639_1 = "de"
        german.iso_639_2 = "deu"
        french = Language.create_with_entity(db_session, "Q150", "French")
        french.iso_639_1 = "fr"
        french.iso_639_2 = "fra"

        # Create Wikipedia projects
        en_wiki = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wiki.official_website = "https://en.wikipedia.org"
        de_wiki = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        de_wiki.official_website = "https://de.wikipedia.org"
        fr_wiki = WikipediaProject.create_with_entity(
            db_session, "Q8447", "French Wikipedia"
        )
        fr_wiki.official_website = "https://fr.wikipedia.org"

        # Add language relations
        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$lang-en",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=german.wikidata_id,
                child_entity_id=de_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q48183$lang-de",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=french.wikidata_id,
                child_entity_id=fr_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q8447$lang-fr",
            )
        )
        db_session.flush()

        # Create politicians
        politician1 = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999888", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", "Third Politician"
        )
        db_session.flush()

        # English: 3 links
        db_session.add(
            WikipediaSource(
                politician_id=politician1.id,
                url="https://en.wikipedia.org/wiki/P1",
                wikipedia_project_id=en_wiki.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician2.id,
                url="https://en.wikipedia.org/wiki/P2",
                wikipedia_project_id=en_wiki.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician3.id,
                url="https://en.wikipedia.org/wiki/P3",
                wikipedia_project_id=en_wiki.wikidata_id,
            )
        )

        # German: 2 links
        db_session.add(
            WikipediaSource(
                politician_id=politician1.id,
                url="https://de.wikipedia.org/wiki/P1",
                wikipedia_project_id=de_wiki.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician2.id,
                url="https://de.wikipedia.org/wiki/P2",
                wikipedia_project_id=de_wiki.wikidata_id,
            )
        )

        # French: 1 link
        db_session.add(
            WikipediaSource(
                politician_id=politician3.id,
                url="https://fr.wikipedia.org/wiki/P3",
                wikipedia_project_id=fr_wiki.wikidata_id,
            )
        )

        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Verify counts
        language_counts = {
            lang["wikidata_id"]: lang["sources_count"] for lang in languages
        }

        assert language_counts["Q1860"] == 3  # English
        assert language_counts["Q188"] == 2  # German
        assert language_counts["Q150"] == 1  # French

    def test_languages_ordered_by_source_count_desc(
        self, client, mock_auth, db_session
    ):
        """Languages should be ordered by sources_count descending."""
        # Create languages
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        german = Language.create_with_entity(db_session, "Q188", "German")
        german.iso_639_1 = "de"
        german.iso_639_2 = "deu"

        # Create Wikipedia projects
        en_wiki = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wiki.official_website = "https://en.wikipedia.org"
        de_wiki = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        de_wiki.official_website = "https://de.wikipedia.org"

        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$lang-en",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=german.wikidata_id,
                child_entity_id=de_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q48183$lang-de",
            )
        )
        db_session.flush()

        # Create politicians
        politician1 = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999888", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", "Third Politician"
        )
        db_session.flush()

        # English: 1 link
        db_session.add(
            WikipediaSource(
                politician_id=politician1.id,
                url="https://en.wikipedia.org/wiki/P1",
                wikipedia_project_id=en_wiki.wikidata_id,
            )
        )

        # German: 3 links
        db_session.add(
            WikipediaSource(
                politician_id=politician1.id,
                url="https://de.wikipedia.org/wiki/P1",
                wikipedia_project_id=de_wiki.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician2.id,
                url="https://de.wikipedia.org/wiki/P2",
                wikipedia_project_id=de_wiki.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician3.id,
                url="https://de.wikipedia.org/wiki/P3",
                wikipedia_project_id=de_wiki.wikidata_id,
            )
        )

        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Find German and English in the results
        german_result = next(
            (lang for lang in languages if lang["wikidata_id"] == "Q188")
        )
        english_result = next(
            (lang for lang in languages if lang["wikidata_id"] == "Q1860")
        )

        # German should come before English due to higher count
        german_index = languages.index(german_result)
        english_index = languages.index(english_result)
        assert german_index < english_index

    def test_languages_filters_soft_deleted(self, client, mock_auth, db_session):
        """Soft-deleted languages should not appear in results."""
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        db_session.flush()

        # Soft delete the language's WikidataEntity
        db_session.refresh(language)
        language.wikidata_entity.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Sample language should not be in results
        assert not any(lang["wikidata_id"] == "Q1860" for lang in languages)

    def test_languages_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/languages")
        assert response.status_code == 401


class TestGetCountries:
    """Test the GET /countries endpoint."""

    def test_countries_with_no_citizenships(self, client, mock_auth, db_session):
        """Countries with no citizenship properties should not appear in results."""
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()
        # Should be empty since no countries have citizenships
        assert len(countries) == 0

    def test_countries_with_citizenships(self, client, mock_auth, db_session):
        """Countries should count citizenship properties."""
        # Create countries
        usa = Country.create_with_entity(db_session, "Q30", "United States")
        usa.iso_code = "US"
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        france = Country.create_with_entity(db_session, "Q142", "France")
        france.iso_code = "FR"

        # Create politicians
        politician1 = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", "Third Politician"
        )
        db_session.flush()

        # US: 3 citizenships
        db_session.add(
            Property(
                politician_id=politician1.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=usa.wikidata_id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician2.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=usa.wikidata_id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician3.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=usa.wikidata_id,
            )
        )

        # Germany: 2 citizenships
        db_session.add(
            Property(
                politician_id=politician1.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician2.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )

        # France: 1 citizenship
        db_session.add(
            Property(
                politician_id=politician3.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=france.wikidata_id,
            )
        )

        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        # Verify counts
        country_counts = {
            ctry["wikidata_id"]: ctry["citizenships_count"] for ctry in countries
        }

        assert country_counts["Q30"] == 3  # US
        assert country_counts["Q183"] == 2  # Germany
        assert country_counts["Q142"] == 1  # France

    def test_countries_ordered_by_citizenship_count_desc(
        self, client, mock_auth, db_session
    ):
        """Countries should be ordered by citizenships_count descending."""
        # Create countries
        usa = Country.create_with_entity(db_session, "Q30", "United States")
        usa.iso_code = "US"
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"

        # Create politicians
        politician1 = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", "Third Politician"
        )
        db_session.flush()

        # Germany: 3 citizenships
        db_session.add(
            Property(
                politician_id=politician1.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician2.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician3.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )

        # US: 1 citizenship
        db_session.add(
            Property(
                politician_id=politician1.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=usa.wikidata_id,
            )
        )

        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        # Find Germany and US in the results
        germany_result = next(
            (ctry for ctry in countries if ctry["wikidata_id"] == "Q183")
        )
        us_result = next((ctry for ctry in countries if ctry["wikidata_id"] == "Q30"))

        # Germany should come before US due to higher count
        germany_index = countries.index(germany_result)
        us_index = countries.index(us_result)
        assert germany_index < us_index

    def test_countries_filters_soft_deleted(self, client, mock_auth, db_session):
        """Soft-deleted countries should not appear in results."""
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

        # Soft delete the country's WikidataEntity
        db_session.refresh(country)
        country.wikidata_entity.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        # Sample country should not be in results
        assert not any(ctry["wikidata_id"] == "Q30" for ctry in countries)

    def test_countries_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/countries")
        assert response.status_code == 401


class TestCreateEntityEndpoint:
    """Test the create_entity_endpoint factory function via /positions and /locations."""

    def test_positions_basic_retrieval(self, client, mock_auth, db_session):
        """Should retrieve positions with basic metadata."""
        Position.create_with_entity(db_session, "Q30185", "Test Position")
        db_session.flush()

        response = client.get("/positions", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        assert len(positions) == 1

        pos = positions[0]
        assert pos["wikidata_id"] == "Q30185"
        assert pos["name"] == "Test Position"

    def test_positions_with_limit(self, client, mock_auth, db_session):
        """Should respect limit parameter."""
        # Create 5 positions
        for i in range(5):
            Position.create_with_entity(db_session, f"Q{i}", f"Position {i}")
        db_session.flush()

        response = client.get("/positions?limit=3", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        assert len(positions) == 3

    def test_positions_with_offset(self, client, mock_auth, db_session):
        """Should respect offset parameter."""
        # Create 5 positions
        for i in range(5):
            Position.create_with_entity(db_session, f"Q{i}", f"Position {i}")
        db_session.flush()

        # Get all positions
        response_all = client.get("/positions?limit=5", headers=mock_auth)
        all_positions = response_all.json()

        # Get positions with offset=2
        response_offset = client.get("/positions?offset=2&limit=3", headers=mock_auth)
        offset_positions = response_offset.json()

        # Should skip first 2 positions
        assert len(offset_positions) == 3
        assert offset_positions[0]["wikidata_id"] == all_positions[2]["wikidata_id"]

    def test_positions_with_search(self, client, mock_auth, db_session):
        """Should filter positions by search query using fuzzy matching."""
        # Create positions with different names and labels
        Position.create_with_entity(
            db_session,
            "Q1",
            "Mayor of Springfield",
            labels=["Mayor", "Springfield Mayor"],
        )
        Position.create_with_entity(
            db_session,
            "Q2",
            "Governor of California",
            labels=["Governor", "CA Governor"],
        )
        Position.create_with_entity(
            db_session, "Q3", "President", labels=["POTUS", "President of USA"]
        )
        db_session.flush()

        # Search for "mayor"
        response = client.get("/positions?search=mayor", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        # Should find only the mayor position
        assert len(positions) == 1
        assert positions[0]["wikidata_id"] == "Q1"

    def test_positions_filters_soft_deleted(self, client, mock_auth, db_session):
        """Should filter out soft-deleted positions."""
        # Create two positions
        Position.create_with_entity(db_session, "Q1", "Active Position")
        pos2 = Position.create_with_entity(db_session, "Q2", "Deleted Position")
        db_session.flush()

        # Soft delete pos2
        db_session.refresh(pos2)
        pos2.wikidata_entity.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get("/positions", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        assert len(positions) == 1
        assert positions[0]["wikidata_id"] == "Q1"

    def test_locations_basic_retrieval(self, client, mock_auth, db_session):
        """Should retrieve locations with basic metadata."""
        Location.create_with_entity(db_session, "Q28513", "Test Location")
        db_session.flush()

        response = client.get("/locations", headers=mock_auth)
        assert response.status_code == 200

        locations = response.json()
        assert len(locations) == 1

        loc = locations[0]
        assert loc["wikidata_id"] == "Q28513"
        assert loc["name"] == "Test Location"

    def test_locations_with_search(self, client, mock_auth, db_session):
        """Should filter locations by search query using fuzzy matching."""
        # Create locations with different names and labels
        Location.create_with_entity(
            db_session,
            "Q1",
            "Springfield, Illinois",
            labels=["Springfield", "Springfield IL"],
        )
        Location.create_with_entity(
            db_session,
            "Q2",
            "Los Angeles",
            labels=["LA", "City of Angels"],
        )
        db_session.flush()

        # Search for "springfield"
        response = client.get("/locations?search=springfield", headers=mock_auth)
        assert response.status_code == 200

        locations = response.json()
        # Should find only Springfield
        assert len(locations) == 1
        assert locations[0]["wikidata_id"] == "Q1"

    def test_positions_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/positions")
        assert response.status_code == 401

    def test_locations_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/locations")
        assert response.status_code == 401

    def test_positions_limit_validation(self, client, mock_auth):
        """Should validate limit parameter (max 1000)."""
        response = client.get("/positions?limit=1001", headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_positions_offset_validation(self, client, mock_auth):
        """Should validate offset parameter (must be >= 0)."""
        response = client.get("/positions?offset=-1", headers=mock_auth)
        assert response.status_code == 422  # Validation error

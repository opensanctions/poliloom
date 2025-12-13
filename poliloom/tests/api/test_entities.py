"""Tests for the entities API endpoints (languages, countries, positions, locations)."""


class TestGetLanguages:
    """Test the GET /languages endpoint."""

    def test_languages_with_wikipedia_links(
        self,
        client,
        mock_auth,
        sample_language,
        sample_german_language,
        sample_french_language,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        sample_french_wikipedia_project,
        create_wikipedia_link,
        db_session,
    ):
        """Languages should count Wikipedia links through WikipediaProject relations."""
        # Create politicians with Wikipedia links in different languages
        from poliloom.models import Politician

        politician2 = Politician.create_with_entity(
            db_session, "Q999888", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", "Third Politician"
        )
        db_session.flush()

        # English: 3 links
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(politician2, sample_wikipedia_project)
        create_wikipedia_link(politician3, sample_wikipedia_project)

        # German: 2 links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(politician2, sample_german_wikipedia_project)

        # French: 1 link
        create_wikipedia_link(politician3, sample_french_wikipedia_project)

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
        self,
        client,
        mock_auth,
        sample_language,
        sample_german_language,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        db_session,
    ):
        """Languages should be ordered by sources_count descending."""
        # Create more German links than English
        from poliloom.models import Politician

        politician2 = Politician.create_with_entity(
            db_session, "Q999888", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", "Third Politician"
        )
        db_session.flush()

        # English: 1 link
        create_wikipedia_link(sample_politician, sample_wikipedia_project)

        # German: 3 links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(politician2, sample_german_wikipedia_project)
        create_wikipedia_link(politician3, sample_german_wikipedia_project)

        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Find German and English in the results
        german = next((lang for lang in languages if lang["wikidata_id"] == "Q188"))
        english = next((lang for lang in languages if lang["wikidata_id"] == "Q1860"))

        # German should come before English due to higher count
        german_index = languages.index(german)
        english_index = languages.index(english)
        assert german_index < english_index

    def test_languages_filters_soft_deleted(
        self,
        client,
        mock_auth,
        sample_language,
        db_session,
    ):
        """Soft-deleted languages should not appear in results."""
        from datetime import datetime, timezone

        # Soft delete the language's WikidataEntity
        sample_language.wikidata_entity.deleted_at = datetime.now(timezone.utc)
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

    def test_countries_with_no_citizenships(self, client, mock_auth, sample_country):
        """Countries with no citizenship properties should not appear in results."""
        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()
        # Should be empty since no countries have citizenships
        assert len(countries) == 0

    def test_countries_with_citizenships(
        self,
        client,
        mock_auth,
        sample_country,
        sample_germany_country,
        sample_france_country,
        create_citizenship,
        db_session,
    ):
        """Countries should count citizenship properties."""
        from poliloom.models import Politician

        # Create politicians
        politician1 = Politician.create_with_entity(
            db_session, "Q999888", "First Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", "Third Politician"
        )
        db_session.flush()

        # US: 3 citizenships
        create_citizenship(politician1, sample_country)
        create_citizenship(politician2, sample_country)
        create_citizenship(politician3, sample_country)

        # Germany: 2 citizenships
        create_citizenship(politician1, sample_germany_country)
        create_citizenship(politician2, sample_germany_country)

        # France: 1 citizenship
        create_citizenship(politician3, sample_france_country)

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
        self,
        client,
        mock_auth,
        sample_country,
        sample_germany_country,
        create_citizenship,
        db_session,
    ):
        """Countries should be ordered by citizenships_count descending."""
        from poliloom.models import Politician

        politician1 = Politician.create_with_entity(
            db_session, "Q999888", "First Politician"
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", "Second Politician"
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", "Third Politician"
        )
        db_session.flush()

        # Germany: 3 citizenships
        create_citizenship(politician1, sample_germany_country)
        create_citizenship(politician2, sample_germany_country)
        create_citizenship(politician3, sample_germany_country)

        # US: 1 citizenship
        create_citizenship(politician1, sample_country)

        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        # Find Germany and US in the results
        germany = next((ctry for ctry in countries if ctry["wikidata_id"] == "Q183"))
        us = next((ctry for ctry in countries if ctry["wikidata_id"] == "Q30"))

        # Germany should come before US due to higher count
        germany_index = countries.index(germany)
        us_index = countries.index(us)
        assert germany_index < us_index

    def test_countries_filters_soft_deleted(
        self,
        client,
        mock_auth,
        sample_country,
        db_session,
    ):
        """Soft-deleted countries should not appear in results."""
        from datetime import datetime, timezone

        # Soft delete the country's WikidataEntity
        sample_country.wikidata_entity.deleted_at = datetime.now(timezone.utc)
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

    def test_positions_basic_retrieval(
        self, client, mock_auth, sample_position, db_session
    ):
        """Should retrieve positions with basic metadata."""
        response = client.get("/positions", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        assert len(positions) == 1

        position = positions[0]
        assert position["wikidata_id"] == "Q30185"
        assert position["name"] == "Test Position"

    def test_positions_with_limit(self, client, mock_auth, db_session):
        """Should respect limit parameter."""
        from poliloom.models import Position

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
        from poliloom.models import Position

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

    def test_positions_filters_soft_deleted(self, client, mock_auth, db_session):
        """Should filter out soft-deleted positions."""
        from poliloom.models import Position
        from datetime import datetime, timezone

        # Create two positions
        Position.create_with_entity(db_session, "Q1", "Active Position")
        pos2 = Position.create_with_entity(db_session, "Q2", "Deleted Position")
        db_session.flush()

        # Soft delete pos2
        pos2.wikidata_entity.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get("/positions", headers=mock_auth)
        assert response.status_code == 200

        positions = response.json()
        assert len(positions) == 1
        assert positions[0]["wikidata_id"] == "Q1"

    def test_locations_basic_retrieval(
        self, client, mock_auth, sample_location, db_session
    ):
        """Should retrieve locations with basic metadata."""
        response = client.get("/locations", headers=mock_auth)
        assert response.status_code == 200

        locations = response.json()
        assert len(locations) == 1

        location = locations[0]
        assert location["wikidata_id"] == "Q28513"
        assert location["name"] == "Test Location"

    def test_locations_with_search(self, client, mock_auth, db_session):
        """Should filter locations by search query using fuzzy matching."""
        from poliloom.models import Location

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

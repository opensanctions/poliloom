"""Tests for the preferences API endpoint."""

import pytest
from unittest.mock import AsyncMock, Mock as SyncMock, patch
from fastapi.testclient import TestClient

from poliloom.api import app
from poliloom.api.auth import User
from poliloom.models import (
    Preference,
    PreferenceType,
    Country,
    Language,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication for tests."""
    with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
        mock_user = User(user_id=12345, jwt_token="valid_jwt_token")
        mock_oauth_handler = SyncMock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        yield {"Authorization": "Bearer valid_jwt_token"}


@pytest.fixture
def sample_country_preference(db_session, sample_country):
    """Create a sample country preference."""
    preference = Preference(
        user_id="12345",
        preference_type=PreferenceType.COUNTRY,
        entity_id=sample_country.wikidata_id,
    )
    db_session.add(preference)
    db_session.flush()
    return preference


@pytest.fixture
def sample_language_preference(db_session, sample_language):
    """Create a sample language preference."""
    preference = Preference(
        user_id="12345",
        preference_type=PreferenceType.LANGUAGE,
        entity_id=sample_language.wikidata_id,
    )
    db_session.add(preference)
    db_session.flush()
    return preference


@pytest.fixture
def multiple_preferences(db_session, sample_country, sample_language):
    """Create multiple preferences for testing."""
    # Create a second country and language for variety
    country2 = Country.create_with_entity(db_session, "Q183", "Germany")
    country2.iso_code = "DE"
    language2 = Language.create_with_entity(db_session, "Q1321", "Spanish")
    language2.iso_639_1 = "es"
    language2.iso_639_2 = "spa"

    db_session.flush()

    preferences = [
        Preference(
            user_id="12345",
            preference_type=PreferenceType.COUNTRY,
            entity_id=sample_country.wikidata_id,
        ),
        Preference(
            user_id="12345",
            preference_type=PreferenceType.COUNTRY,
            entity_id=country2.wikidata_id,
        ),
        Preference(
            user_id="12345",
            preference_type=PreferenceType.LANGUAGE,
            entity_id=sample_language.wikidata_id,
        ),
        Preference(
            user_id="12345",
            preference_type=PreferenceType.LANGUAGE,
            entity_id=language2.wikidata_id,
        ),
    ]

    db_session.add_all(preferences)
    db_session.flush()
    return preferences


class TestPreferencesEndpoint:
    """Test the preferences API endpoint."""

    def test_get_preferences_requires_auth(self, client):
        """Test that preferences endpoint requires authentication."""
        response = client.get("/preferences")
        assert response.status_code in [401, 403]  # Unauthorized

    def test_get_preferences_empty(self, client, mock_auth, db_session):
        """Test getting preferences when user has none."""
        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()
        assert preferences == []

    def test_get_preferences_single_country(
        self, client, mock_auth, sample_country_preference, sample_country
    ):
        """Test getting preferences with single country preference."""
        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()

        assert len(preferences) == 1
        assert preferences[0]["wikidata_id"] == sample_country.wikidata_id
        assert preferences[0]["name"] == sample_country.name
        assert preferences[0]["preference_type"] == "country"

    def test_get_preferences_single_language(
        self, client, mock_auth, sample_language_preference, sample_language
    ):
        """Test getting preferences with single language preference."""
        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()

        assert len(preferences) == 1
        assert preferences[0]["wikidata_id"] == sample_language.wikidata_id
        assert preferences[0]["name"] == sample_language.name
        assert preferences[0]["preference_type"] == "language"

    def test_get_preferences_multiple_types(
        self, client, mock_auth, multiple_preferences, sample_country, sample_language
    ):
        """Test getting preferences with multiple types in flat list."""
        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()

        # Should return all 4 preferences in a flat list
        assert len(preferences) == 4

        # Verify we have both countries and languages
        country_prefs = [p for p in preferences if p["preference_type"] == "country"]
        language_prefs = [p for p in preferences if p["preference_type"] == "language"]

        assert len(country_prefs) == 2
        assert len(language_prefs) == 2

        # Verify structure of each preference
        for pref in preferences:
            assert "wikidata_id" in pref
            assert "name" in pref
            assert "preference_type" in pref
            assert pref["preference_type"] in ["country", "language"]

    def test_get_preferences_different_user(
        self, client, sample_country_preference, sample_country
    ):
        """Test that preferences are user-specific."""
        # Mock a different user
        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            different_user = User(user_id=67890, jwt_token="different_token")
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=different_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            headers = {"Authorization": "Bearer different_token"}
            response = client.get("/preferences", headers=headers)
            assert response.status_code == 200
            preferences = response.json()

            # Different user should not see the first user's preferences
            assert preferences == []

    def test_get_preferences_missing_entity(self, client, mock_auth, db_session):
        """Test handling of preferences with missing entity references."""
        from poliloom.models import WikidataEntity

        # Create a WikidataEntity without corresponding Country/Language
        orphaned_entity = WikidataEntity(
            wikidata_id="Q99999999", name="Orphaned Entity"
        )
        db_session.add(orphaned_entity)

        # Create a preference referencing this orphaned entity
        preference = Preference(
            user_id="12345",
            preference_type=PreferenceType.COUNTRY,
            entity_id="Q99999999",  # Points to orphaned entity
        )
        db_session.add(preference)
        db_session.flush()

        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()

        # Should include the preference with the orphaned entity
        assert len(preferences) == 1
        assert preferences[0]["wikidata_id"] == "Q99999999"
        assert preferences[0]["name"] == "Orphaned Entity"
        assert preferences[0]["preference_type"] == "country"

    def test_preferences_endpoint_structure(self, client):
        """Test that preferences endpoint exists and has correct structure."""
        # Should fail with auth error, not 404 (not found)
        response = client.get("/preferences")
        assert response.status_code in [401, 403]

    def test_get_preferences_response_schema(
        self, client, mock_auth, sample_country_preference, sample_country
    ):
        """Test that response matches expected schema."""
        response = client.get("/preferences", headers=mock_auth)
        assert response.status_code == 200
        preferences = response.json()

        assert isinstance(preferences, list)
        if preferences:  # If not empty
            pref = preferences[0]
            assert isinstance(pref, dict)
            assert "wikidata_id" in pref
            assert "name" in pref
            assert "preference_type" in pref
            assert isinstance(pref["wikidata_id"], str)
            assert isinstance(pref["name"], str)
            assert isinstance(pref["preference_type"], str)


class TestPreferencesEndpointIntegration:
    """Integration tests for preferences endpoint functionality."""

    def test_preferences_with_real_auth_flow(self, client):
        """Test preferences endpoint behavior in realistic auth scenarios."""
        # Test without auth
        response = client.get("/preferences")
        assert response.status_code in [401, 403]

        # Test with invalid token format
        headers = {"Authorization": "Bearer invalid_format"}
        response = client.get("/preferences", headers=headers)
        assert response.status_code == 401

        # Test with invalid auth scheme
        headers = {"Authorization": "Basic invalid_scheme"}
        response = client.get("/preferences", headers=headers)
        assert response.status_code == 403

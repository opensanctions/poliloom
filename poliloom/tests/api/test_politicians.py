"""Tests for the /politicians endpoint (search/list/get)."""

from poliloom.models import (
    Politician,
)


class TestGetNextPoliticianEndpoint:
    """Test the GET /politicians/next endpoint."""

    def test_returns_next_politician_qid(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that endpoint returns the next unevaluated politician's QID."""
        response = client.get("/politicians/next", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert "wikidata_id" in data
        assert "meta" in data
        assert data["wikidata_id"] == "Q123456"

    def test_returns_null_when_no_politicians(self, client, mock_auth):
        """Test that endpoint returns null when no politicians available."""
        response = client.get("/politicians/next", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert data["wikidata_id"] is None
        assert "meta" in data

    def test_excludes_by_qid(self, client, mock_auth, politician_with_unevaluated_data):
        """Test excluding politicians by Wikidata QID."""
        response = client.get(
            "/politicians/next?exclude_ids=Q123456", headers=mock_auth
        )

        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] is None

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians/next")
        assert response.status_code in [401, 403]

    def test_meta_has_expected_fields(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that meta includes enrichment status fields."""
        response = client.get("/politicians/next", headers=mock_auth)
        data = response.json()

        assert "has_enrichable_politicians" in data["meta"]
        assert "total_matching_filters" in data["meta"]


class TestGetPoliticianByQidEndpoint:
    """Test the GET /politicians/{qid} endpoint."""

    def test_returns_politician(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test fetching a politician by QID."""
        response = client.get("/politicians/Q123456", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Test Politician"
        assert data["wikidata_id"] == "Q123456"
        assert "properties" in data
        assert isinstance(data["properties"], list)

    def test_returns_404_for_unknown_qid(self, client, mock_auth):
        """Test that 404 is returned for unknown QID."""
        response = client.get("/politicians/Q999999999", headers=mock_auth)
        assert response.status_code == 404

    def test_returns_all_properties(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that all non-deleted properties are returned."""
        response = client.get("/politicians/Q123456", headers=mock_auth)
        data = response.json()

        # Should have 6 properties (3 extracted + 3 wikidata)
        assert len(data["properties"]) == 6

        property_types = [p["type"] for p in data["properties"]]
        assert "P569" in property_types  # BIRTH_DATE
        assert "P570" in property_types  # DEATH_DATE
        assert "P39" in property_types  # POSITION
        assert "P19" in property_types  # BIRTHPLACE

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians/Q123456")
        assert response.status_code in [401, 403]


class TestSearchPoliticiansEndpoint:
    """Test the GET /politicians/search endpoint."""

    def test_search_by_name(self, client, mock_auth, db_session):
        """Test searching politicians by name."""
        # Create a politician with a unique name and label for search
        politician = Politician.create_with_entity(
            db_session,
            "Q999888",
            "Unique Search Test Name",
            labels=["Unique Search Test Name"],
        )
        db_session.add(politician)
        db_session.flush()

        response = client.get(
            "/politicians/search?q=Unique%20Search%20Test", headers=mock_auth
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # The search result should include our politician
        names = [p["name"] for p in data]
        assert "Unique Search Test Name" in names

    def test_search_requires_query(self, client, mock_auth):
        """Test that search endpoint requires a query parameter."""
        response = client.get("/politicians/search", headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_search_requires_authentication(self, client):
        """Test that search endpoint requires authentication."""
        response = client.get("/politicians/search?q=test")
        assert response.status_code in [401, 403]

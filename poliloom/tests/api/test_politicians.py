"""Tests for the /politicians endpoint (search/list)."""

from poliloom.models import (
    Politician,
    Property,
    PropertyType,
)


class TestGetPoliticiansEndpoint:
    """Test the GET /politicians endpoint for unevaluated politicians."""

    def test_returns_wrapped_response(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that endpoint returns a PoliticiansListResponse."""
        response = client.get("/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        # Should be wrapped in {"politicians": [...], "meta": {...}}
        assert "politicians" in data
        assert "meta" in data
        assert isinstance(data["politicians"], list)

        # Meta should have expected fields
        assert "has_enrichable_politicians" in data["meta"]
        assert "total_matching_filters" in data["meta"]

        # Each politician should have expected fields
        if len(data["politicians"]) >= 1:
            politician = data["politicians"][0]
            assert "id" in politician
            assert "name" in politician
            assert "wikidata_id" in politician
            assert "properties" in politician

    def test_pagination(self, client, mock_auth, db_session):
        """Test pagination with limit and offset."""
        # Create multiple politicians with unevaluated extracted properties
        for i in range(5):
            politician = Politician.create_with_entity(
                db_session, f"Q{800000 + i}", f"Pagination Test {i}"
            )
            db_session.add(politician)
            db_session.flush()

            # Add unevaluated property (no statement_id = extracted)
            prop = Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value=f"+196{i}-00-00T00:00:00Z",
                value_precision=9,
            )
            db_session.add(prop)
        db_session.flush()

        # Test limit
        response = client.get("/politicians?limit=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

        # Test offset
        response = client.get("/politicians?limit=2&offset=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians")
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

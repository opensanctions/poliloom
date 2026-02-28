"""Tests for the source page endpoints (GET/PATCH /archived-pages/{id})."""

from unittest.mock import patch


class TestGetSourcePage:
    """Test the GET /archived-pages/{id} endpoint."""

    def test_requires_authentication(self, client, sample_archived_page):
        """Test that endpoint requires authentication."""
        response = client.get(f"/archived-pages/{sample_archived_page.id}")
        assert response.status_code in [401, 403]

    def test_not_found_for_unknown_uuid(self, client, mock_auth):
        """Test 404 for unknown archived page UUID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        response = client.get(f"/archived-pages/{fake_uuid}", headers=mock_auth)
        assert response.status_code == 404

    def test_empty_politicians_when_no_references(
        self, client, mock_auth, sample_archived_page
    ):
        """Test that an archived page with no property references returns empty politicians list."""
        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert data["archived_page"]["id"] == str(sample_archived_page.id)
        assert data["archived_page"]["url"] == sample_archived_page.url
        assert data["politicians"] == []

    def test_returns_politician_with_properties(
        self,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
    ):
        """Test that properties referencing this page are returned with the politician."""
        create_birth_date(
            sample_politician,
            value="1980-01-01",
            archived_page=sample_archived_page,
            supporting_quotes=["born in 1980"],
        )

        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert politician["wikidata_id"] == "Q123456"
        assert politician["name"] == "Test Politician"
        assert len(politician["properties"]) == 1

        prop = politician["properties"][0]
        assert prop["type"] == "P569"
        assert prop["value"] == "1980-01-01"
        assert len(prop["sources"]) == 1
        assert prop["sources"][0]["supporting_quotes"] == ["born in 1980"]

    def test_multiple_properties_grouped_under_one_politician(
        self,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
        create_citizenship,
        sample_country,
    ):
        """Test multiple properties from same page grouped under one politician."""
        create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        create_citizenship(
            sample_politician, sample_country, archived_page=sample_archived_page
        )

        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert len(data["politicians"][0]["properties"]) == 2

    def test_multiple_politicians_from_same_source(
        self,
        db_session,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
    ):
        """Test multiple politicians with properties from the same page."""
        from poliloom.models import Politician

        politician2 = Politician.create_with_entity(
            db_session, "Q789012", "Second Politician"
        )
        db_session.flush()

        create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        create_birth_date(
            politician2, value="1990-05-15", archived_page=sample_archived_page
        )

        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        qids = {p["wikidata_id"] for p in data["politicians"]}
        assert qids == {"Q123456", "Q789012"}

    def test_soft_deleted_properties_excluded(
        self,
        db_session,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
    ):
        """Test that soft-deleted properties are excluded."""
        from datetime import datetime, timezone

        prop = create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        prop.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert data["politicians"] == []

    def test_only_matching_source_in_property(
        self,
        db_session,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
    ):
        """Test that properties only include the matching source, not all sources."""
        from poliloom.models import ArchivedPage, PropertyReference
        from datetime import datetime, timezone

        # Create a second archived page
        other_page = ArchivedPage(
            url="https://example.com/other",
            content_hash="other123",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(other_page)
        db_session.flush()

        # Create property with reference to the first page
        prop = create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        # Add a second reference to the other page
        ref2 = PropertyReference(
            property_id=prop.id,
            archived_page_id=other_page.id,
        )
        db_session.add(ref2)
        db_session.flush()

        # Query by first page — should only see the first page's reference
        response = client.get(
            f"/archived-pages/{sample_archived_page.id}", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        prop_data = data["politicians"][0]["properties"][0]
        assert len(prop_data["sources"]) == 1
        assert prop_data["sources"][0]["archived_page"]["id"] == str(
            sample_archived_page.id
        )


class TestPatchSourceProperties:
    """Test the PATCH /archived-pages/{id}/properties endpoint."""

    def test_requires_authentication(self, client, sample_archived_page):
        """Test that endpoint requires authentication."""
        data = {"items": {}}
        response = client.patch(
            f"/archived-pages/{sample_archived_page.id}/properties", json=data
        )
        assert response.status_code in [401, 403]

    def test_not_found_for_unknown_uuid(self, client, mock_auth):
        """Test 404 for unknown archived page UUID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {"items": {}}
        response = client.patch(
            f"/archived-pages/{fake_uuid}/properties",
            json=data,
            headers=mock_auth,
        )
        assert response.status_code == 404

    def test_accept_reject_works(
        self,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
        create_citizenship,
        sample_country,
    ):
        """Test accept/reject via source endpoint."""
        prop1 = create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        prop2 = create_citizenship(
            sample_politician, sample_country, archived_page=sample_archived_page
        )

        data = {
            "items": {
                str(sample_politician.id): [
                    {"action": "accept", "id": str(prop1.id)},
                    {"action": "reject", "id": str(prop2.id)},
                ]
            }
        }
        response = client.patch(
            f"/archived-pages/{sample_archived_page.id}/properties",
            json=data,
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "2 items" in result["message"]

    @patch("poliloom.api.politicians.push_evaluation")
    def test_create_works_with_politician_id(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
    ):
        """Test creating a property via source endpoint using politician ID key."""
        mock_push_evaluation.return_value = True

        data = {
            "items": {
                str(sample_politician.id): [
                    {
                        "action": "create",
                        "type": "P569",
                        "value": "+1985-03-20T00:00:00Z",
                        "value_precision": 11,
                    }
                ]
            }
        }
        response = client.patch(
            f"/archived-pages/{sample_archived_page.id}/properties",
            json=data,
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "1 items" in result["message"]

    def test_multiple_politicians_in_one_request(
        self,
        db_session,
        client,
        mock_auth,
        sample_politician,
        sample_archived_page,
        create_birth_date,
    ):
        """Test submitting actions for multiple politicians in one request."""
        from poliloom.models import Politician

        politician2 = Politician.create_with_entity(
            db_session, "Q789012", "Second Politician"
        )
        db_session.flush()

        prop1 = create_birth_date(
            sample_politician, value="1980-01-01", archived_page=sample_archived_page
        )
        prop2 = create_birth_date(
            politician2, value="1990-05-15", archived_page=sample_archived_page
        )

        data = {
            "items": {
                str(sample_politician.id): [{"action": "accept", "id": str(prop1.id)}],
                str(politician2.id): [{"action": "reject", "id": str(prop2.id)}],
            }
        }
        response = client.patch(
            f"/archived-pages/{sample_archived_page.id}/properties",
            json=data,
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "2 items" in result["message"]

    def test_create_with_nonexistent_politician(
        self, client, mock_auth, sample_archived_page
    ):
        """Test create with a politician ID that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        data = {
            "items": {
                fake_id: [
                    {
                        "action": "create",
                        "type": "P569",
                        "value": "+1985-03-20T00:00:00Z",
                        "value_precision": 11,
                    }
                ]
            }
        }
        response = client.patch(
            f"/archived-pages/{sample_archived_page.id}/properties",
            json=data,
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert any(f"{fake_id} not found" in e for e in result["errors"])

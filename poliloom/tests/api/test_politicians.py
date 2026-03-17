"""Tests for the /politicians endpoint (search/list/get/patch)."""

from unittest.mock import patch

from poliloom.models import (
    Evaluation,
    Politician,
)
from poliloom.sse import EvaluationCountEvent


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


class TestPatchProperties:
    """Test the PATCH /politicians/{qid}/properties endpoint."""

    def test_accept_reject_existing_properties(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test accepting and rejecting existing properties."""
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [
                {
                    "action": "accept",
                    "id": str(test_properties[0].id),
                },
                {
                    "action": "reject",
                    "id": str(test_properties[1].id),
                },
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "2 items" in result["message"]

    def test_missing_action_returns_422(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that items without action field return 422."""
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [
                {"id": str(test_properties[0].id)},
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 422

    def test_invalid_action_returns_422(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that items with invalid action return 422."""
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [
                {"action": "invalid", "id": str(test_properties[0].id)},
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 422

    def test_accept_nonexistent_property(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test accept with nonexistent property ID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {
            "items": [{"action": "accept", "id": fake_uuid}],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert f"Property {fake_uuid} not found" in result["errors"]

    def test_nonexistent_politician_qid(self, client, mock_auth):
        """Test PATCH with nonexistent politician QID."""
        data = {
            "items": [
                {"action": "accept", "id": "11111111-1111-1111-1111-111111111111"}
            ],
        }
        response = client.patch(
            "/politicians/Q999999/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 404

    @patch("poliloom.api.politicians.push_evaluation")
    def test_mixed_valid_invalid_properties(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test with mix of valid and invalid property IDs."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {
            "items": [
                {"action": "accept", "id": str(test_properties[0].id)},
                {"action": "reject", "id": fake_uuid},
                {"action": "accept", "id": str(test_properties[1].id)},
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert "2 items" in result["message"]
        assert len(result["errors"]) == 1
        assert f"Property {fake_uuid} not found" in result["errors"][0]

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        data = {
            "items": [
                {"action": "accept", "id": "11111111-1111-1111-1111-111111111111"}
            ],
        }
        response = client.patch("/politicians/Q123456/properties", json=data)
        assert response.status_code in [401, 403]

    def test_empty_items_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test with empty items list."""
        data = {"items": []}
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "0 items" in result["message"]

    @patch("poliloom.api.politicians.push_evaluation")
    def test_accept_with_wikidata_push(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test that accepted evaluations are pushed to Wikidata."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [{"action": "accept", "id": str(test_properties[0].id)}],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.politicians.push_evaluation")
    def test_wikidata_push_failure(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test handling of Wikidata push failures."""
        mock_push_evaluation.side_effect = Exception("Wikidata API error")
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [{"action": "accept", "id": str(test_properties[0].id)}],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert any("Wikidata API error" in error for error in result["errors"])

    @patch("poliloom.api.politicians.push_evaluation")
    def test_create_date_property(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test creating a new date property."""
        mock_push_evaluation.return_value = True

        data = {
            "items": [
                {
                    "action": "create",
                    "type": "P569",
                    "value": "+1985-03-20T00:00:00Z",
                    "value_precision": 11,
                }
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.politicians.push_evaluation")
    def test_create_entity_property(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
        sample_position,
    ):
        """Test creating a new entity property."""
        mock_push_evaluation.return_value = True

        data = {
            "items": [
                {
                    "action": "create",
                    "type": "P39",
                    "entity_id": sample_position.wikidata_id,
                    "qualifiers": {
                        "P580": [
                            {
                                "datavalue": {
                                    "value": {
                                        "time": "+2020-01-01T00:00:00Z",
                                        "precision": 11,
                                    }
                                }
                            }
                        ]
                    },
                }
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("poliloom.api.politicians.push_evaluation")
    def test_mixed_accept_and_create(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test submitting both accept/reject and create items in one request."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "items": [
                {"action": "accept", "id": str(test_properties[0].id)},
                {
                    "action": "create",
                    "type": "P569",
                    "value": "+1990-06-15T00:00:00Z",
                    "value_precision": 11,
                },
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "2 items" in result["message"]

    def test_create_with_invalid_type(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test creating a property with an invalid type."""
        data = {
            "items": [
                {
                    "action": "create",
                    "type": "P999",
                    "value": "test",
                }
            ],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200
        result = response.json()
        assert any("Unknown property type" in e for e in result["errors"])

    def test_create_missing_type(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test creating a property without specifying type returns 422."""
        data = {
            "items": [{"action": "create", "value": "test"}],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 422

    def test_accept_without_id_returns_422(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that accept without id returns 422."""
        data = {
            "items": [{"action": "accept"}],
        }
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 422

    @patch("poliloom.api.politicians.push_evaluation")
    @patch("poliloom.api.politicians.notify")
    def test_emits_evaluation_count_event(
        self,
        mock_notify,
        mock_push_evaluation,
        client,
        mock_auth,
        db_session,
        politician_with_unevaluated_data,
    ):
        """Test that accepting a property emits an EvaluationCountEvent."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        prop = next(p for p in politician.properties if p.statement_id is None)

        data = {"items": [{"action": "accept", "id": str(prop.id)}]}
        response = client.patch(
            "/politicians/Q123456/properties", json=data, headers=mock_auth
        )
        assert response.status_code == 200

        mock_notify.assert_called_once()
        event = mock_notify.call_args[0][0]
        assert isinstance(event, EvaluationCountEvent)
        assert event.total == db_session.query(Evaluation).count()

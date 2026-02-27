"""Tests for the PATCH /politicians/{qid}/properties endpoint."""

from unittest.mock import patch


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

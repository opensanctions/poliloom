"""Tests for the evaluations API endpoint."""

from unittest.mock import patch


class TestEvaluationsEndpoint:
    """Test the evaluations API endpoint."""

    def test_evaluate_existing_properties(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluating existing properties with new unified format."""
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        # Old format should NOT work
        old_format = {
            "evaluations": [{"id": str(test_properties[0].id), "is_accepted": True}]
        }
        response = client.post("/evaluations/", json=old_format, headers=mock_auth)
        assert response.status_code == 422  # Validation error

        # New format should work
        new_format = {
            "politician_id": str(politician.id),
            "items": [
                {"id": str(test_properties[0].id), "is_accepted": True},
                {"id": str(test_properties[1].id), "is_accepted": False},
            ],
        }
        response = client.post("/evaluations/", json=new_format, headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["evaluations"]) == 2

        # Verify each evaluation has required fields
        for evaluation in data["evaluations"]:
            assert "id" in evaluation
            assert "user_id" in evaluation
            assert "is_accepted" in evaluation
            assert "property_id" in evaluation
            assert "created_at" in evaluation

    def test_evaluate_nonexistent_property(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation with nonexistent property ID."""
        politician = politician_with_unevaluated_data
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {
            "politician_id": str(politician.id),
            "items": [{"id": fake_uuid, "is_accepted": True}],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200  # Should succeed but with errors
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert len(result["errors"]) > 0
        assert f"Property {fake_uuid} not found" in result["errors"]

    def test_evaluate_nonexistent_politician(self, client, mock_auth):
        """Test evaluation with nonexistent politician ID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {
            "politician_id": fake_uuid,
            "items": [
                {"id": "11111111-1111-1111-1111-111111111111", "is_accepted": True}
            ],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 404

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_mixed_valid_invalid_properties(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test evaluation with mix of valid and invalid property IDs."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        fake_uuid = "99999999-9999-9999-9999-999999999999"
        data = {
            "politician_id": str(politician.id),
            "items": [
                {"id": str(test_properties[0].id), "is_accepted": True},
                {"id": fake_uuid, "is_accepted": False},
                {"id": str(test_properties[1].id), "is_accepted": True},
            ],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 2
        assert len(result["errors"]) == 1
        assert f"Property {fake_uuid} not found" in result["errors"][0]

    def test_evaluate_requires_authentication(self, client):
        """Test that evaluation endpoint requires authentication."""
        data = {
            "politician_id": "11111111-1111-1111-1111-111111111111",
            "items": [
                {"id": "11111111-1111-1111-1111-111111111111", "is_accepted": True}
            ],
        }
        response = client.post("/evaluations/", json=data)
        assert response.status_code in [401, 403]

    def test_evaluate_empty_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation with empty items list."""
        politician = politician_with_unevaluated_data
        data = {"politician_id": str(politician.id), "items": []}
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert result["success"] is True

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test that evaluations are pushed to Wikidata when accepted."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "politician_id": str(politician.id),
            "items": [{"id": str(test_properties[0].id), "is_accepted": True}],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push_failure(
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
            "politician_id": str(politician.id),
            "items": [{"id": str(test_properties[0].id), "is_accepted": True}],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1
        assert len(result["errors"]) > 0
        assert any("Wikidata API error" in error for error in result["errors"])

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_create_new_date_property(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test creating a new date property via submission."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data

        data = {
            "politician_id": str(politician.id),
            "items": [
                {
                    "type": "P569",
                    "value": "+1985-03-20T00:00:00Z",
                    "value_precision": 11,
                }
            ],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1
        assert result["evaluations"][0]["is_accepted"] is True
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_create_new_entity_property(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
        sample_position,
    ):
        """Test creating a new entity property via submission."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data

        data = {
            "politician_id": str(politician.id),
            "items": [
                {
                    "type": "P39",
                    "entity_id": sample_position.wikidata_id,
                    "qualifiers_json": {
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
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1
        assert result["evaluations"][0]["is_accepted"] is True

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_mixed_evaluation_and_creation(
        self,
        mock_push_evaluation,
        client,
        mock_auth,
        politician_with_unevaluated_data,
    ):
        """Test submitting both evaluations and new properties in one request."""
        mock_push_evaluation.return_value = True
        politician = politician_with_unevaluated_data
        test_properties = [p for p in politician.properties if p.statement_id is None]

        data = {
            "politician_id": str(politician.id),
            "items": [
                # Evaluate existing
                {"id": str(test_properties[0].id), "is_accepted": True},
                # Create new
                {
                    "type": "P569",
                    "value": "+1990-06-15T00:00:00Z",
                    "value_precision": 11,
                },
            ],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 2
        assert result["success"] is True

    def test_create_with_invalid_type(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test creating a property with an invalid type."""
        politician = politician_with_unevaluated_data
        data = {
            "politician_id": str(politician.id),
            "items": [
                {
                    "type": "P999",
                    "value": "test",
                }
            ],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert any("Unknown property type" in e for e in result["errors"])

    def test_create_missing_type(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test creating a property without specifying type."""
        politician = politician_with_unevaluated_data
        data = {
            "politician_id": str(politician.id),
            "items": [{"value": "test"}],
        }
        response = client.post("/evaluations/", json=data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert any("missing 'type'" in e for e in result["errors"])

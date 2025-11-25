"""Tests for the evaluations API endpoint."""

from unittest.mock import patch


class TestEvaluationsEndpoint:
    """Test the evaluations API endpoint."""

    def test_evaluate_single_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation accepts single list format."""
        politician, test_properties = politician_with_unevaluated_data

        # Old format should NOT work
        old_format = {
            "property_evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True}
            ],
            "position_evaluations": [],
            "birthplace_evaluations": [],
        }
        response = client.post("/evaluations/", json=old_format, headers=mock_auth)
        assert response.status_code == 422  # Validation error

        # New format should work
        new_format = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True},
                {"id": str(test_properties[1].id), "is_accepted": False},
            ]
        }
        response = client.post("/evaluations/", json=new_format, headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["evaluations"]) == 2

        # Verify evaluation objects are returned
        eval_ids = {e["id"] for e in data["evaluations"]}
        assert len(eval_ids) == 2  # Two unique evaluation IDs

        # Verify each evaluation has required fields
        for evaluation in data["evaluations"]:
            assert "id" in evaluation
            assert "user_id" in evaluation
            assert "is_accepted" in evaluation
            assert "property_id" in evaluation
            assert "created_at" in evaluation

    def test_evaluate_nonexistent_property(self, client, mock_auth):
        """Test evaluation with nonexistent property ID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": fake_uuid, "is_accepted": True}  # Nonexistent ID
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should succeed but with errors
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert len(result["errors"]) > 0
        assert f"Property {fake_uuid} not found" in result["errors"]

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_mixed_valid_invalid_properties(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation with mix of valid and invalid property IDs."""
        mock_push_evaluation.return_value = True
        politician, test_properties = politician_with_unevaluated_data

        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True},  # Valid
                {"id": fake_uuid, "is_accepted": False},  # Invalid
                {"id": str(test_properties[1].id), "is_accepted": True},  # Valid
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 2  # Only valid properties evaluated
        assert len(result["errors"]) == 1
        assert f"Property {fake_uuid} not found" in result["errors"][0]

    def test_evaluate_requires_authentication(self, client):
        """Test that evaluation endpoint requires authentication."""
        evaluation_data = {
            "evaluations": [
                {"id": "11111111-1111-1111-1111-111111111111", "is_accepted": True}
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data)
        assert response.status_code in [401, 403]  # Unauthorized

    def test_evaluate_empty_list(self, client, mock_auth):
        """Test evaluation with empty evaluations list."""
        evaluation_data = {"evaluations": []}
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert result["success"] is True

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that evaluations are pushed to Wikidata when accepted."""
        mock_push_evaluation.return_value = True
        politician, test_properties = politician_with_unevaluated_data

        evaluation_data = {
            "evaluations": [{"id": str(test_properties[0].id), "is_accepted": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1

        # Verify push_evaluation was called
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push_failure(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test handling of Wikidata push failures."""
        mock_push_evaluation.side_effect = Exception("Wikidata API error")
        politician, test_properties = politician_with_unevaluated_data

        evaluation_data = {
            "evaluations": [{"id": str(test_properties[0].id), "is_accepted": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should still succeed locally
        result = response.json()
        assert len(result["evaluations"]) == 1
        assert len(result["errors"]) > 0
        assert any("Wikidata API error" in error for error in result["errors"])

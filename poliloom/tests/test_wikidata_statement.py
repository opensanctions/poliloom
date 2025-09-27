"""Tests for wikidata_statement module functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from poliloom.models import Property, PropertyType, Politician, Evaluation
from poliloom.wikidata_statement import (
    _convert_qualifiers_to_rest_api,
    delete_statement,
    create_statement,
    push_evaluation,
)


class TestConvertQualifiersToRestApi:
    """Test qualifiers format conversion from Action API to REST API."""

    def test_time_qualifiers(self):
        """Test conversion of time qualifiers (P580, P582)."""
        action_format = {
            "P580": [
                {
                    "hash": "b2ac2678b4dc96ac36ce5ff2db5c9a0d6aa2144e",
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2017-05-21T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P582": [
                {
                    "hash": "947c3a6e8d560fb5b357b778369e5f4e1e1a6a78",
                    "datatype": "time",
                    "property": "P582",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2019-02-04T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P580"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2017-05-21T00:00:00Z",
                        "after": 0,
                        "before": 0,
                        "timezone": 0,
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
            {
                "property": {"id": "P582"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2019-02-04T00:00:00Z",
                        "after": 0,
                        "before": 0,
                        "timezone": 0,
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
        ]

        assert result == expected

    def test_wikibase_item_qualifiers(self):
        """Test conversion of wikibase-item qualifiers (P1365, P1366)."""
        action_format = {
            "P1365": [
                {
                    "hash": "3df8181e4ff20601e6234c3ffa71eac73b2e2a3b",
                    "datatype": "wikibase-item",
                    "property": "P1365",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "wikibase-entityid",
                        "value": {
                            "id": "Q65423352",
                            "numeric-id": 65423352,
                            "entity-type": "item",
                        },
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1365"},
                "value": {"type": "value", "content": "Q65423352"},
            }
        ]

        assert result == expected

    def test_string_qualifiers(self):
        """Test conversion of string qualifiers (P1545)."""
        action_format = {
            "P1545": [
                {
                    "hash": "cbff8d4b3b7b35f905ef3147a7a6cb88845a774f",
                    "datatype": "string",
                    "property": "P1545",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "4"},
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {"property": {"id": "P1545"}, "value": {"type": "value", "content": "4"}}
        ]

        assert result == expected

    def test_somevalue_qualifiers(self):
        """Test conversion of somevalue qualifiers."""
        action_format = {
            "P580": [
                {
                    "hash": "abc123",
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "somevalue",
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [{"property": {"id": "P580"}, "value": {"type": "somevalue"}}]

        assert result == expected

    def test_novalue_qualifiers(self):
        """Test conversion of novalue qualifiers."""
        action_format = {
            "P582": [
                {
                    "hash": "def456",
                    "datatype": "time",
                    "property": "P582",
                    "snaktype": "novalue",
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [{"property": {"id": "P582"}, "value": {"type": "novalue"}}]

        assert result == expected

    def test_mixed_qualifiers(self):
        """Test conversion with multiple qualifier types."""
        action_format = {
            "P580": [
                {
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2017-05-21T00:00:00Z",
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P1545": [
                {
                    "datatype": "string",
                    "property": "P1545",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "4"},
                }
            ],
            "P1365": [
                {
                    "datatype": "wikibase-item",
                    "property": "P1365",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "wikibase-entityid",
                        "value": {
                            "id": "Q65423352",
                            "numeric-id": 65423352,
                            "entity-type": "item",
                        },
                    },
                }
            ],
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        # Should have 3 qualifiers
        assert len(result) == 3

        # Check each qualifier exists with correct structure
        property_ids = [q["property"]["id"] for q in result]
        assert "P580" in property_ids
        assert "P1545" in property_ids
        assert "P1365" in property_ids

    def test_quantity_qualifiers(self):
        """Test conversion of quantity qualifiers (P1111)."""
        action_format = {
            "P1111": [
                {
                    "hash": "d0a0f2fb6654bb991907f65ddfc979a1e3fddcfa",
                    "datatype": "quantity",
                    "property": "P1111",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "quantity",
                        "value": {"unit": "1", "amount": "+314963"},
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1111"},
                "value": {
                    "type": "value",
                    "content": {"unit": "1", "amount": "+314963"},
                },
            }
        ]

        assert result == expected

    def test_external_id_qualifiers(self):
        """Test conversion of external-id qualifiers (P5002)."""
        action_format = {
            "P5002": [
                {
                    "hash": "0e4c138c94b5ccb299139e088b0878d2a4aaa6d4",
                    "datatype": "external-id",
                    "property": "P5002",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "199887"},
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P5002"},
                "value": {"type": "value", "content": "199887"},
            }
        ]

        assert result == expected

    def test_monolingualtext_qualifiers(self):
        """Test conversion of monolingualtext qualifiers (P6375)."""
        action_format = {
            "P6375": [
                {
                    "hash": "e702ce63a07977d232d6114b33d7b734f4079121",
                    "datatype": "monolingualtext",
                    "property": "P6375",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "monolingualtext",
                        "value": {"text": "Rubanda", "language": "en"},
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P6375"},
                "value": {
                    "type": "value",
                    "content": {"text": "Rubanda", "language": "en"},
                },
            }
        ]

        assert result == expected

    def test_commonsmedia_qualifiers(self):
        """Test conversion of commonsMedia qualifiers (P94)."""
        action_format = {
            "P94": [
                {
                    "hash": "2c4e3b501fc36d5c0b5bd304bcc759f9931ccace",
                    "datatype": "commonsMedia",
                    "property": "P94",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "string",
                        "value": "Escudo del Senado de España.svg",
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P94"},
                "value": {
                    "type": "value",
                    "content": "Escudo del Senado de España.svg",
                },
            }
        ]

        assert result == expected

    def test_url_qualifiers(self):
        """Test conversion of url qualifiers (P1065)."""
        action_format = {
            "P1065": [
                {
                    "hash": "77bd2ff4068349bc6a71b1cbcbad23ec01aa15df",
                    "datatype": "url",
                    "property": "P1065",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "string",
                        "value": "https://www.elconfidencial.com/empresas/2022-04-11/planeta-relevo-silvio-gonzalez-consejero-atresmedia_3405523/",
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1065"},
                "value": {
                    "type": "value",
                    "content": "https://www.elconfidencial.com/empresas/2022-04-11/planeta-relevo-silvio-gonzalez-consejero-atresmedia_3405523/",
                },
            }
        ]

        assert result == expected

    def test_empty_qualifiers(self):
        """Test conversion of empty qualifiers."""
        action_format = {}
        result = _convert_qualifiers_to_rest_api(action_format)
        assert result == []


class TestDeleteStatement:
    """Test delete_statement function with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_deletion_200(self):
        """Test successful statement deletion (200 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.delete.return_value = (
                mock_response
            )

            await delete_statement("Q42", "Q42$statement-id", "test_jwt_token")

            # Verify the correct URL was called
            mock_client.return_value.__aenter__.return_value.delete.assert_called_once()
            call_args = (
                mock_client.return_value.__aenter__.return_value.delete.call_args
            )
            assert "Q42/statements/Q42$statement-id" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_already_deleted_404(self):
        """Test deletion when statement already deleted (404 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client.return_value.__aenter__.return_value.delete.return_value = (
                mock_response
            )

            # Should not raise exception for 404 (already deleted)
            await delete_statement("Q42", "Q42$statement-id", "test_jwt_token")

    @pytest.mark.asyncio
    async def test_authentication_error_401(self):
        """Test authentication error (401 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_client.return_value.__aenter__.return_value.delete.return_value = (
                mock_response
            )

            with pytest.raises(Exception, match="Failed to delete statement.*HTTP 401"):
                await delete_statement("Q42", "Q42$statement-id", "test_jwt_token")

    @pytest.mark.asyncio
    async def test_server_error_500(self):
        """Test server error (500 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.return_value.__aenter__.return_value.delete.return_value = (
                mock_response
            )

            with pytest.raises(Exception, match="Failed to delete statement.*HTTP 500"):
                await delete_statement("Q42", "Q42$statement-id", "test_jwt_token")

    @pytest.mark.asyncio
    async def test_missing_jwt_token(self):
        """Test missing JWT token raises ValueError."""
        with pytest.raises(ValueError, match="JWT token is required"):
            await delete_statement("Q42", "Q42$statement-id", "")

        with pytest.raises(ValueError, match="JWT token is required"):
            await delete_statement("Q42", "Q42$statement-id", None)

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Test network error handling."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.delete.side_effect = (
                httpx.RequestError("Network error")
            )

            with pytest.raises(httpx.RequestError):
                await delete_statement("Q42", "Q42$statement-id", "test_jwt_token")


class TestCreateStatement:
    """Test create_statement function with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_creation_201(self):
        """Test successful statement creation (201 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "Q42$new-statement-id"}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            result = await create_statement(
                "Q42", "P39", value, jwt_token="test_jwt_token"
            )

            assert result == "Q42$new-statement-id"

            # Verify the correct URL was called
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert "Q42/statements" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_creation_with_qualifiers_and_references(self):
        """Test statement creation with qualifiers and references."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "Q42$new-statement-id"}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            qualifiers = [
                {
                    "property": {"id": "P580"},
                    "value": {"type": "value", "content": "2020"},
                }
            ]
            references = [
                {
                    "property": {"id": "P854"},
                    "value": {"type": "value", "content": "http://example.com"},
                }
            ]

            result = await create_statement(
                "Q42",
                "P39",
                value,
                qualifiers=qualifiers,
                references=references,
                jwt_token="test_jwt_token",
            )

            assert result == "Q42$new-statement-id"

            # Check that request included qualifiers and references
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            request_data = call_args.kwargs["json"]
            assert "qualifiers" in request_data["statement"]
            assert "references" in request_data["statement"]

    @pytest.mark.asyncio
    async def test_validation_error_400(self):
        """Test validation error (400 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invalid value"
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "invalid"}
            with pytest.raises(Exception, match="Failed to create statement.*HTTP 400"):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_authentication_error_401(self):
        """Test authentication error (401 response)."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(Exception, match="Failed to create statement.*HTTP 401"):
                await create_statement("Q42", "P39", value, jwt_token="invalid_token")

    @pytest.mark.asyncio
    async def test_missing_jwt_token(self):
        """Test missing JWT token raises ValueError."""
        value = {"type": "value", "content": "Q123"}

        with pytest.raises(ValueError, match="JWT token is required"):
            await create_statement("Q42", "P39", value, jwt_token="")

        with pytest.raises(ValueError, match="JWT token is required"):
            await create_statement("Q42", "P39", value, jwt_token=None)

    @pytest.mark.asyncio
    async def test_missing_statement_id_in_response(self):
        """Test missing statement ID in successful response."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {}  # Missing "id" field
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(Exception, match="No statement ID returned"):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Test network error handling."""
        with patch("poliloom.wikidata_statement.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                httpx.RequestError("Network error")
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(httpx.RequestError):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")


class TestPushEvaluation:
    """Test push_evaluation function with mocked database and HTTP calls."""

    def create_mock_evaluation(
        self,
        is_confirmed=True,
        property_type=PropertyType.POSITION,
        has_statement_id=False,
        has_archived_page_id=False,
    ):
        """Helper to create mock evaluation objects."""
        # Create mock politician
        politician = Mock(spec=Politician)
        politician.wikidata_id = "Q12345"

        # Create mock property
        property_mock = Mock(spec=Property)
        property_mock.type = property_type
        property_mock.statement_id = "Q12345$statement-id" if has_statement_id else None
        property_mock.archived_page_id = (
            "archived-page-id" if has_archived_page_id else None
        )
        property_mock.politician = politician
        property_mock.qualifiers_json = None
        property_mock.references_json = None
        property_mock.deleted_at = None  # Initialize as None for testing

        # Set appropriate values based on property type
        if property_type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            property_mock.value = "1985-03-15"
            property_mock.entity_id = None
        else:
            property_mock.value = None
            property_mock.entity_id = "Q67890"

        # Create mock evaluation
        evaluation = Mock(spec=Evaluation)
        evaluation.id = "eval-123"
        evaluation.is_confirmed = is_confirmed
        evaluation.property = property_mock

        return evaluation

    @pytest.mark.asyncio
    async def test_confirmed_extracted_data_creates_statement(self):
        """Test confirmed evaluation of extracted data creates new statement."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=True,
            property_type=PropertyType.POSITION,
            has_statement_id=False,  # No statement_id = extracted data
            has_archived_page_id=True,  # Has archived_page_id = extracted data
        )

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.create_statement", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = "Q12345$new-statement-id"

            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is True
            mock_create.assert_called_once()

            # Verify the statement was created with correct parameters
            call_args = mock_create.call_args
            assert call_args[0][0] == "Q12345"  # politician_wikidata_id
            assert call_args[0][1] == "P39"  # PropertyType.POSITION.value
            assert call_args[0][2] == {
                "type": "value",
                "content": "Q67890",
            }  # entity_id

            # Verify property was updated with statement ID
            assert evaluation.property.statement_id == "Q12345$new-statement-id"
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_negative_existing_statement_deletes_and_soft_deletes(self):
        """Test negative evaluation of existing statement deletes from Wikidata and soft deletes."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=False,
            property_type=PropertyType.POSITION,
            has_statement_id=True,  # Has statement_id = existing statement
            has_archived_page_id=False,  # No archived_page_id = existing statement
        )

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.delete_statement", new_callable=AsyncMock
        ) as mock_delete:
            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is True
            mock_delete.assert_called_once_with(
                "Q12345", "Q12345$statement-id", "test_jwt_token"
            )

            # Verify property was soft deleted
            assert evaluation.property.deleted_at is not None
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_negative_extracted_data_soft_deletes_only(self):
        """Test negative evaluation of extracted data only soft deletes."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=False,
            property_type=PropertyType.POSITION,
            has_statement_id=False,  # No statement_id = extracted data
            has_archived_page_id=True,  # Has archived_page_id = extracted data
        )

        mock_db = Mock()

        result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

        assert result is True

        # Verify property was soft deleted
        assert evaluation.property.deleted_at is not None
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_confirmed_existing_statement_no_action(self):
        """Test confirmed evaluation of existing statement takes no action."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=True,
            property_type=PropertyType.POSITION,
            has_statement_id=True,  # Has statement_id = existing statement
            has_archived_page_id=False,  # No archived_page_id = existing statement
        )

        mock_db = Mock()

        result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

        assert result is True
        # Should not modify anything
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_date_property_handling(self):
        """Test handling of date properties (birth/death dates)."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=True,
            property_type=PropertyType.BIRTH_DATE,
            has_statement_id=False,
            has_archived_page_id=True,
        )

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.create_statement", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = "Q12345$new-statement-id"

            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is True

            # Verify the statement was created with date value
            call_args = mock_create.call_args
            assert call_args[0][1] == "P569"  # PropertyType.BIRTH_DATE.value
            assert call_args[0][2] == {
                "type": "value",
                "content": "1985-03-15",
            }  # value

    @pytest.mark.asyncio
    async def test_wikidata_deletion_failure_prevents_soft_delete(self):
        """Test that Wikidata deletion failure prevents soft delete."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=False,
            property_type=PropertyType.POSITION,
            has_statement_id=True,
            has_archived_page_id=False,
        )

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.delete_statement", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = Exception("API Error")

            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is False

            # Verify property was NOT soft deleted
            assert evaluation.property.deleted_at is None
            mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_statement_failure_returns_false(self):
        """Test that create_statement failure returns False."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=True,
            property_type=PropertyType.POSITION,
            has_statement_id=False,
            has_archived_page_id=True,
        )

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.create_statement", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API Error")

            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is False

    @pytest.mark.asyncio
    async def test_qualifiers_conversion_and_passing(self):
        """Test that qualifiers are converted and passed to create_statement."""
        evaluation = self.create_mock_evaluation(
            is_confirmed=True,
            property_type=PropertyType.POSITION,
            has_statement_id=False,
            has_archived_page_id=True,
        )

        # Add qualifiers in Action API format
        evaluation.property.qualifiers_json = {
            "P580": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {"time": "+2020-01-01T00:00:00Z"},
                    },
                }
            ]
        }
        evaluation.property.references_json = [{"some": "reference"}]

        mock_db = Mock()

        with patch(
            "poliloom.wikidata_statement.create_statement", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = "Q12345$new-statement-id"

            result = await push_evaluation(evaluation, "test_jwt_token", mock_db)

            assert result is True

            # Verify qualifiers were converted and passed
            call_args = mock_create.call_args
            qualifiers = call_args.kwargs["qualifiers"]
            assert len(qualifiers) == 1
            assert qualifiers[0]["property"]["id"] == "P580"
            assert qualifiers[0]["value"]["type"] == "value"

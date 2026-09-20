"""Tests for wikidata_statement module functionality."""

from unittest.mock import Mock, patch

import httpx2
import pytest

from poliloom.wikidata.statement import (
    WikidataApiError,
    create_entity,
    create_statement,
)


class TestCreateEntity:
    """Test create_entity function with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_creation_201(self):
        """Test successful entity creation (201 response)."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "Q123456"}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            result = await create_entity("Test Label", jwt_token="test_jwt_token")

            assert result == "Q123456"

            # Verify the correct URL was called
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert "entities/items" in call_args[0][0]

            # Verify labels are sent for both en and mul
            request_data = call_args.kwargs["json"]
            assert request_data["item"]["labels"] == {
                "en": "Test Label",
                "mul": "Test Label",
            }
            assert "descriptions" not in request_data["item"]

    @pytest.mark.asyncio
    async def test_creation_with_description(self):
        """Test entity creation includes an en description when provided."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "Q123456"}
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            await create_entity(
                "Test Label", description="A test description", jwt_token="token"
            )

            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            request_data = call_args.kwargs["json"]
            assert request_data["item"]["descriptions"] == {"en": "A test description"}

    @pytest.mark.asyncio
    async def test_validation_error_400(self):
        """Test validation error (400 response)."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invalid label"
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with pytest.raises(
                WikidataApiError, match="Failed to create entity.*HTTP 400"
            ):
                await create_entity("Test Label", jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_missing_jwt_token(self):
        """Test missing JWT token raises ValueError."""
        with pytest.raises(ValueError, match="JWT token is required"):
            await create_entity("Test Label", jwt_token="")

        with pytest.raises(ValueError, match="JWT token is required"):
            await create_entity("Test Label", jwt_token=None)

    @pytest.mark.asyncio
    async def test_missing_entity_id_in_response(self):
        """Test missing entity ID in successful response."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {}  # Missing "id" field
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with pytest.raises(WikidataApiError, match="No entity ID returned"):
                await create_entity("Test Label", jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Test network error handling."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                httpx2.RequestError("Network error")
            )

            with pytest.raises(httpx2.RequestError):
                await create_entity("Test Label", jwt_token="test_jwt_token")


class TestCreateStatement:
    """Test create_statement function with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_creation_201(self):
        """Test successful statement creation (201 response)."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
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
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
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
                    "parts": [
                        {
                            "property": {"id": "P854"},
                            "value": {"type": "value", "content": "http://example.com"},
                        }
                    ]
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
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invalid value"
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "invalid"}
            with pytest.raises(
                WikidataApiError, match="Failed to create statement.*HTTP 400"
            ):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_authentication_error_401(self):
        """Test authentication error (401 response)."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(
                WikidataApiError, match="Failed to create statement.*HTTP 401"
            ):
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
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {}  # Missing "id" field
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(WikidataApiError, match="No statement ID returned"):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Test network error handling."""
        with patch("poliloom.wikidata.statement.httpx2.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                httpx2.RequestError("Network error")
            )

            value = {"type": "value", "content": "Q123"}
            with pytest.raises(httpx2.RequestError):
                await create_statement("Q42", "P39", value, jwt_token="test_jwt_token")

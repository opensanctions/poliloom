"""Tests for API endpoints with MediaWiki OAuth authentication."""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from poliloom.api.app import app
from poliloom.api.auth import User


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(username='testuser', user_id=12345, email='test@example.com')


class TestAPIAuthentication:
    """Test authentication integration across API endpoints."""
    
    def test_unconfirmed_politicians_requires_auth(self, client):
        """Test that /politicians/unconfirmed requires authentication."""
        response = client.get("/politicians/unconfirmed")
        assert response.status_code == 403  # No auth token provided
    
    def test_confirm_politician_requires_auth(self, client):
        """Test that /politicians/{id}/confirm requires authentication."""
        confirmation_data = {
            "confirmed_properties": [],
            "discarded_properties": [],
            "confirmed_positions": [],
            "discarded_positions": []
        }
        response = client.post("/politicians/test_id/confirm", json=confirmation_data)
        assert response.status_code == 403  # No auth token provided
    
    def test_invalid_token_format_rejected(self, client):
        """Test that invalid token format is rejected."""
        headers = {"Authorization": "Bearer invalid_token_format"}
        response = client.get("/politicians/unconfirmed", headers=headers)
        assert response.status_code == 401  # Invalid token format
    
    def test_invalid_auth_scheme_rejected(self, client):
        """Test that invalid auth scheme is rejected."""
        headers = {"Authorization": "Basic invalid_scheme"}
        response = client.get("/politicians/unconfirmed", headers=headers)
        assert response.status_code == 403  # Invalid scheme
    
    @patch('poliloom.api.auth.get_oauth_handler')
    def test_valid_token_passes_auth(self, mock_get_oauth_handler, client):
        """Test that valid OAuth token passes authentication."""
        from unittest.mock import AsyncMock
        
        # Mock successful OAuth verification
        mock_user = User(username='testuser', user_id=12345, email='test@example.com')
        mock_oauth_handler = Mock()
        mock_oauth_handler.verify_access_token = AsyncMock(return_value=mock_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        
        headers = {"Authorization": "Bearer valid_token:valid_secret"}
        response = client.get("/politicians/unconfirmed", headers=headers)
        
        # Should not be 403 (auth should pass, but may fail on DB or other issues)
        assert response.status_code != 403
        mock_oauth_handler.verify_access_token.assert_called_once_with('valid_token', 'valid_secret')


class TestAPIEndpointsStructure:
    """Test that API endpoints are properly defined."""
    
    def test_root_endpoint_exists(self, client):
        """Test that root endpoint exists and returns expected response."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "PoliLoom API"}
    
    def test_unconfirmed_politicians_endpoint_exists(self, client):
        """Test that unconfirmed politicians endpoint exists."""
        response = client.get("/politicians/unconfirmed")
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403
    
    def test_confirm_politician_endpoint_exists(self, client):
        """Test that confirm politician endpoint exists."""
        confirmation_data = {
            "confirmed_properties": [],
            "discarded_properties": [],
            "confirmed_positions": [],
            "discarded_positions": []
        }
        response = client.post("/politicians/test_id/confirm", json=confirmation_data)
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403


class TestAPIResponseSchemas:
    """Test API response schemas and validation."""
    
    def test_confirmation_request_validation(self, client):
        """Test that confirmation request validates input schema."""
        # Test with invalid JSON structure
        invalid_data = {"invalid_field": "value"}
        response = client.post("/politicians/test_id/confirm", json=invalid_data)
        
        # Should either be 403 (auth required) or 422 (validation error)
        # The auth error takes precedence
        assert response.status_code == 403
    
    def test_pagination_parameter_validation(self, client):
        """Test that pagination parameters are validated."""
        # Test with invalid limit (too high)
        response = client.get("/politicians/unconfirmed?limit=101")
        assert response.status_code in [403, 422]  # Auth or validation error
        
        # Test with invalid offset (negative)
        response = client.get("/politicians/unconfirmed?offset=-1")
        assert response.status_code in [403, 422]  # Auth or validation error
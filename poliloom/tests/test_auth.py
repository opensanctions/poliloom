"""Tests for MediaWiki OAuth authentication."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from poliloom.api.auth import MediaWikiOAuth, get_current_user, get_optional_user, User


class TestMediaWikiOAuth:
    """Test MediaWiki OAuth handler."""
    
    @patch.dict('os.environ', {
        'MEDIAWIKI_CONSUMER_KEY': 'test_key',
        'MEDIAWIKI_CONSUMER_SECRET': 'test_secret'
    })
    def test_init_success(self):
        """Test successful initialization with environment variables."""
        oauth = MediaWikiOAuth()
        assert oauth.consumer_key == 'test_key'
        assert oauth.consumer_secret == 'test_secret'
        assert oauth.user_agent == 'PoliLoom API/0.1.0'
    
    @patch.dict('os.environ', {}, clear=True)
    def test_init_missing_credentials(self):
        """Test initialization failure with missing credentials."""
        with pytest.raises(ValueError, match="MediaWiki OAuth credentials not configured"):
            MediaWikiOAuth()
    
    @patch.dict('os.environ', {
        'MEDIAWIKI_CONSUMER_KEY': 'test_key',
        'MEDIAWIKI_CONSUMER_SECRET': 'test_secret'
    })
    @patch('poliloom.api.auth.jwt.decode')
    async def test_verify_jwt_token_success(self, mock_jwt_decode):
        """Test successful JWT token verification."""
        # Mock successful JWT decode response
        mock_jwt_decode.return_value = {
            'username': 'testuser',
            'sub': 12345,
            'email': 'test@example.com'
        }
        
        oauth = MediaWikiOAuth()
        user = await oauth.verify_jwt_token('test_jwt_token')
        
        assert isinstance(user, User)
        assert user.username == 'testuser'
        assert user.user_id == 12345
        assert user.email == 'test@example.com'
        
        # Verify jwt.decode was called with correct parameters
        mock_jwt_decode.assert_called_once_with(
            'test_jwt_token', 
            key="", 
            audience='test_key',
            options={"verify_signature": False, "verify_nbf": False}
        )
    
    @patch.dict('os.environ', {
        'MEDIAWIKI_CONSUMER_KEY': 'test_key',
        'MEDIAWIKI_CONSUMER_SECRET': 'test_secret'
    })
    @patch('poliloom.api.auth.jwt.decode')
    async def test_verify_jwt_token_failure(self, mock_jwt_decode):
        """Test JWT token verification failure."""
        # Mock failed JWT decode
        mock_jwt_decode.side_effect = JWTError("Invalid token")
        
        oauth = MediaWikiOAuth()
        
        with pytest.raises(HTTPException) as exc_info:
            await oauth.verify_jwt_token('invalid_jwt_token')
        
        assert exc_info.value.status_code == 401
        assert "Invalid JWT token" in str(exc_info.value.detail)
    
    @patch.dict('os.environ', {
        'MEDIAWIKI_CONSUMER_KEY': 'test_key',
        'MEDIAWIKI_CONSUMER_SECRET': 'test_secret'
    })
    @patch('poliloom.api.auth.jwt.decode')
    async def test_verify_jwt_token_missing_email(self, mock_jwt_decode):
        """Test JWT token verification with missing email field."""
        # Mock JWT decode response without email
        mock_jwt_decode.return_value = {
            'username': 'testuser',
            'sub': 12345
        }
        
        oauth = MediaWikiOAuth()
        user = await oauth.verify_jwt_token('test_jwt_token')
        
        assert isinstance(user, User)
        assert user.username == 'testuser'
        assert user.user_id == 12345
        assert user.email is None


class TestAuthDependencies:
    """Test FastAPI authentication dependencies."""
    
    @patch('poliloom.api.auth.get_oauth_handler')
    async def test_get_current_user_success(self, mock_get_oauth_handler):
        """Test successful user authentication."""
        # Mock successful verification
        expected_user = User(username='testuser', user_id=12345, email='test@example.com')
        mock_oauth_handler = Mock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=expected_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='jwt_token_here'
        )
        
        user = await get_current_user(credentials)
        
        assert user == expected_user
        mock_oauth_handler.verify_jwt_token.assert_called_once_with('jwt_token_here')
    
    @patch('poliloom.api.auth.get_oauth_handler')
    async def test_get_current_user_invalid_jwt(self, mock_get_oauth_handler):
        """Test authentication failure with invalid JWT token."""
        # Mock JWT verification failure
        mock_oauth_handler = Mock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(
            side_effect=HTTPException(status_code=401, detail="Invalid JWT token")
        )
        mock_get_oauth_handler.return_value = mock_oauth_handler
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='invalid_jwt_token'
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Invalid JWT token" in str(exc_info.value.detail)
    
    @patch('poliloom.api.auth.get_oauth_handler')
    async def test_get_current_user_verification_failure(self, mock_get_oauth_handler):
        """Test authentication failure during verification."""
        # Mock verification failure
        mock_oauth_handler = Mock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(
            side_effect=HTTPException(status_code=401, detail="Token verification failed")
        )
        mock_get_oauth_handler.return_value = mock_oauth_handler
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='invalid_jwt_token'
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
    
    @patch('poliloom.api.auth.get_oauth_handler')
    async def test_get_current_user_unexpected_error(self, mock_get_oauth_handler):
        """Test authentication failure with unexpected error."""
        # Mock unexpected error
        mock_oauth_handler = Mock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_get_oauth_handler.return_value = mock_oauth_handler
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='jwt_token_here'
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Authentication failed" in str(exc_info.value.detail)
    
    @patch('poliloom.api.auth.get_current_user')
    async def test_get_optional_user_success(self, mock_get_current_user):
        """Test optional authentication with valid credentials."""
        expected_user = User(username='testuser', user_id=12345)
        mock_get_current_user.return_value = expected_user
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='jwt_token_here'
        )
        
        user = await get_optional_user(credentials)
        assert user == expected_user
    
    async def test_get_optional_user_no_credentials(self):
        """Test optional authentication without credentials."""
        user = await get_optional_user(None)
        assert user is None
    
    @patch('poliloom.api.auth.get_current_user')
    async def test_get_optional_user_auth_failure(self, mock_get_current_user):
        """Test optional authentication with failed credentials."""
        mock_get_current_user.side_effect = HTTPException(
            status_code=401, 
            detail="Authentication failed"
        )
        
        credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials='invalid_jwt_token'
        )
        
        user = await get_optional_user(credentials)
        assert user is None


class TestUserModel:
    """Test User model."""
    
    def test_user_creation_with_email(self):
        """Test User model creation with all fields."""
        user = User(username='testuser', user_id=12345, email='test@example.com')
        assert user.username == 'testuser'
        assert user.user_id == 12345
        assert user.email == 'test@example.com'
    
    def test_user_creation_without_email(self):
        """Test User model creation without email."""
        user = User(username='testuser', user_id=12345)
        assert user.username == 'testuser'
        assert user.user_id == 12345
        assert user.email is None
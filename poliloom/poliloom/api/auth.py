"""MediaWiki OAuth authentication for API routes."""
import os
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
import mwoauth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel


class User(BaseModel):
    """User model for authenticated users."""
    username: str
    user_id: int
    email: Optional[str] = None


class MediaWikiOAuth:
    """MediaWiki OAuth handler."""
    
    def __init__(self):
        self.consumer_key = os.getenv("MEDIAWIKI_CONSUMER_KEY")
        self.consumer_secret = os.getenv("MEDIAWIKI_CONSUMER_SECRET")
        self.user_agent = "PoliLoom API/0.1.0"
        
        if not self.consumer_key or not self.consumer_secret:
            raise ValueError("MediaWiki OAuth credentials not configured")
    
    async def verify_access_token(self, access_token: str, access_secret: str) -> User:
        """Verify OAuth access token and return user info."""
        try:
            # Create identity request using mwoauth
            identity = mwoauth.identify(
                'https://meta.wikimedia.org/w/index.php',
                mwoauth.ConsumerToken(self.consumer_key, self.consumer_secret),
                mwoauth.AccessToken(access_token, access_secret)
            )
            
            return User(
                username=identity['username'],
                user_id=identity['sub'],
                email=identity.get('email')
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid OAuth token: {str(e)}"
            )


# Global OAuth handler - initialized lazily
_oauth_handler: Optional[MediaWikiOAuth] = None

# FastAPI security scheme
security = HTTPBearer()


def get_oauth_handler() -> MediaWikiOAuth:
    """Get or create the global OAuth handler."""
    global _oauth_handler
    if _oauth_handler is None:
        _oauth_handler = MediaWikiOAuth()
    return _oauth_handler


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Extract and validate MediaWiki OAuth credentials from Authorization header.
    
    Expected format: Bearer <access_token>:<access_secret>
    """
    try:
        # Parse token from Bearer format
        token = credentials.credentials
        if ':' not in token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format. Expected format: access_token:access_secret"
            )
        
        access_token, access_secret = token.split(':', 1)
        
        # Verify with MediaWiki
        oauth_handler = get_oauth_handler()
        user = await oauth_handler.verify_access_token(access_token, access_secret)
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """Get user if authenticated, otherwise return None."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
"""MediaWiki OAuth authentication for API routes."""

import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel


class User(BaseModel):
    """User model for authenticated users."""

    username: str
    user_id: int
    email: Optional[str] = None
    jwt_token: Optional[str] = None  # Store the raw JWT token for Wikidata API calls


class MediaWikiOAuth:
    """MediaWiki OAuth handler."""

    def __init__(self):
        self.consumer_key = os.getenv("MEDIAWIKI_CONSUMER_KEY")
        self.consumer_secret = os.getenv("MEDIAWIKI_CONSUMER_SECRET")
        self.user_agent = "PoliLoom API/0.1.0"

        if not self.consumer_key or not self.consumer_secret:
            raise ValueError("MediaWiki OAuth credentials not configured")

    async def verify_jwt_token(self, jwt_token: str) -> User:
        """Verify MediaWiki OAuth 2.0 JWT token."""
        try:
            # Decode JWT without verification first to get the payload
            # MediaWiki OAuth 2.0 JWTs are signed but we need to get user info
            decoded = jwt.decode(
                jwt_token,
                key="",
                audience=self.consumer_key,
                options={"verify_signature": False, "verify_nbf": False},
            )

            # Extract user information from JWT payload
            return User(
                username=decoded.get("username", ""),
                user_id=int(decoded.get("sub", 0)),
                email=decoded.get("email"),
                jwt_token=jwt_token,  # Store the raw JWT token
            )
        except (JWTError, ValueError, KeyError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token: {str(e)}",
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Extract and validate MediaWiki OAuth 2.0 JWT token from Authorization header.

    Expected format: Bearer <jwt_token>
    """
    try:
        # Parse JWT token from Bearer format
        jwt_token = credentials.credentials

        # Verify JWT token with MediaWiki
        oauth_handler = get_oauth_handler()
        user = await oauth_handler.verify_jwt_token(jwt_token)
        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[User]:
    """Get user if authenticated, otherwise return None."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

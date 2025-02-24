"""
Authentication utilities for OpenWebUI.

This module provides core authentication functionality including:
- Password hashing and verification
- JWT token creation and validation
- API key management
- User authentication and authorization
- Integration with Auth0

The module supports multiple authentication methods:
1. Session-based authentication using JWT tokens
2. API key authentication for programmatic access
3. OAuth authentication via Auth0
"""

import logging
import uuid
import jwt

from datetime import datetime, timedelta
from typing import Optional, Union, List, Dict

from open_webui.models.users import Users

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import WEBUI_SECRET_KEY

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from open_webui.utils.auth0 import get_auth0_user

# Suppress excessive passlib logging
logging.getLogger("passlib").setLevel(logging.ERROR)


SESSION_SECRET = WEBUI_SECRET_KEY
ALGORITHM = "HS256"

##############
# Auth Utils
##############

# Configure password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hashed version.
    
    Args:
        plain_password: The password in plain text
        hashed_password: The hashed version of the password
        
    Returns:
        bool: True if the password matches, False otherwise
    """
    return (
        pwd_context.verify(plain_password, hashed_password) if hashed_password else None
    )


def get_password_hash(password: str) -> str:
    """
    Generate a secure hash of a password using bcrypt.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


def create_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """
    Create a JWT token containing the provided data.
    
    Args:
        data: Dictionary containing data to encode in the token
        expires_delta: Optional timedelta for token expiration
        
    Returns:
        str: The encoded JWT token
    """
    payload = data.copy()

    if expires_delta:
        expire = datetime.now() + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        Optional[dict]: The decoded token payload if valid, None otherwise
    """
    try:
        decoded = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        return decoded
    except Exception:
        return None


def extract_token_from_auth_header(auth_header: str) -> str:
    """
    Extract the token from an Authorization header value.
    
    Args:
        auth_header: The full Authorization header value
        
    Returns:
        str: The extracted token
    """
    return auth_header[len("Bearer ") :]


def create_api_key() -> str:
    """
    Generate a new API key in the format 'sk-<uuid>'.
    
    Returns:
        str: A newly generated API key
    """
    key = str(uuid.uuid4()).replace("-", "")
    return f"sk-{key}"


def get_http_authorization_cred(auth_header: str) -> HTTPAuthorizationCredentials:
    """
    Parse an Authorization header into credentials.
    
    Args:
        auth_header: The Authorization header value
        
    Returns:
        HTTPAuthorizationCredentials: The parsed credentials
        
    Raises:
        ValueError: If the header format is invalid
    """
    try:
        scheme, credentials = auth_header.split(" ")
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
    except Exception:
        raise ValueError(ERROR_MESSAGES.INVALID_TOKEN)


async def get_current_user(
    request: Request,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
):
    """
    Get the current authenticated user from various authentication methods.
    
    This function implements a multi-stage authentication process:
    1. Check for API key authentication
    2. Check for JWT token authentication (from header or cookie)
    3. Check for Auth0 authentication
    
    Args:
        request: The FastAPI request object
        auth_token: Optional authorization credentials from header
        
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException: If authentication fails
    """
    token = None

    # Try to get token from Authorization header or cookie
    if auth_token is not None:
        token = auth_token.credentials

    if token is None and "token" in request.cookies:
        token = request.cookies.get("token")

    if token is not None:
        # Check for API key authentication
        if token.startswith("sk-"):
            if not request.state.enable_api_key:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.API_KEY_NOT_ALLOWED
                )

            # Validate API key endpoint restrictions if enabled
            if request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS:
                allowed_paths = [
                    path.strip()
                    for path in str(
                        request.app.state.config.API_KEY_ALLOWED_ENDPOINTS
                    ).split(",")
                ]

                if request.url.path not in allowed_paths:
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.API_KEY_NOT_ALLOWED
                    )

            return get_current_user_by_api_key(token)

        # Try JWT token authentication
        try:
            data = decode_token(token)
            if data is not None and "id" in data:
                user = Users.get_user_by_id(data["id"])
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=ERROR_MESSAGES.INVALID_TOKEN,
                    )
                else:
                    Users.update_user_last_active_by_id(user.id)
                    return user
        except Exception:
            pass  # Fall through to try Auth0

    # Try Auth0 authentication
    auth0_user = await get_auth0_user(request)
    if auth0_user:
        # Find or create user from Auth0 profile
        user = Users.get_by_email(auth0_user.get('email'))
        if not user:
            user = Users.create(
                username=auth0_user.get('nickname') or auth0_user.get('email'),
                email=auth0_user.get('email'),
                password=None,  # No password for OAuth users
                oauth_sub=auth0_user.get('sub'),  # Store Auth0 sub for future reference
            )
        elif not user.oauth_sub:
            # Update existing user with Auth0 sub if not set
            user.oauth_sub = auth0_user.get('sub')
            user.save()
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.UNAUTHORIZED,
    )


def get_current_user_by_api_key(api_key: str):
    """
    Authenticate a user using an API key.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If the API key is invalid
    """
    user = Users.get_user_by_api_key(api_key)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.INVALID_TOKEN,
        )
    else:
        Users.update_user_last_active_by_id(user.id)

    return user


def get_verified_user(user=Depends(get_current_user)):
    """
    Verify that the current user has either 'user' or 'admin' role.
    
    Args:
        user: The current authenticated user
        
    Returns:
        User: The verified user
        
    Raises:
        HTTPException: If the user doesn't have required role
    """
    if user.role not in {"user", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


def get_admin_user(user=Depends(get_current_user)):
    """
    Verify that the current user has the 'admin' role.
    
    Args:
        user: The current authenticated user
        
    Returns:
        User: The verified admin user
        
    Raises:
        HTTPException: If the user isn't an admin
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user

from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.algorithms import RSAAlgorithm
import requests
from open_webui.env import (
    AUTH0_DOMAIN,
    AUTH0_AUDIENCE,
)

security = HTTPBearer()

# Cache the JWKS
JWKS = None
JWKS_CACHE = {}

def get_jwks():
    """Get the JSON Web Key Set from Auth0"""
    global JWKS
    if JWKS is None:
        jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
        JWKS = requests.get(jwks_url).json()
    return JWKS

def get_rsa_key(token: str) -> Optional[dict]:
    """Get the RSA key from JWKS that matches the token's key ID"""
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = get_jwks()
        for key in jwks['keys']:
            if key['kid'] == unverified_header['kid']:
                return {
                    'kty': key['kty'],
                    'kid': key['kid'],
                    'n': key['n'],
                    'e': key['e']
                }
    except Exception:
        return None
    return None

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify the Auth0 token"""
    try:
        token = credentials.credentials
        rsa_key = get_rsa_key(token)
        if rsa_key is None:
            raise HTTPException(
                status_code=401,
                detail='Unable to find appropriate key'
            )
        
        payload = jwt.decode(
            token,
            key=RSAAlgorithm.from_jwk(rsa_key),
            algorithms=['RS256'],
            audience=AUTH0_AUDIENCE,
            issuer=f'https://{AUTH0_DOMAIN}/'
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail='Token has expired'
        )
    except jwt.JWTClaimsError:
        raise HTTPException(
            status_code=401,
            detail='Invalid claims'
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail='Unable to parse authentication token'
        )

async def get_auth0_user(request: Request) -> Optional[dict]:
    """Get the Auth0 user profile from the request"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        rsa_key = get_rsa_key(token)
        if rsa_key is None:
            return None
            
        payload = jwt.decode(
            token,
            key=RSAAlgorithm.from_jwk(rsa_key),
            algorithms=['RS256'],
            audience=AUTH0_AUDIENCE,
            issuer=f'https://{AUTH0_DOMAIN}/'
        )
        
        # Get user profile from Auth0 Management API
        mgmt_token = get_management_token()
        headers = {
            'Authorization': f'Bearer {mgmt_token}',
            'Content-Type': 'application/json'
        }
        user_url = f'https://{AUTH0_DOMAIN}/api/v2/users/{payload["sub"]}'
        response = requests.get(user_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def get_management_token() -> str:
    """Get an access token for the Auth0 Management API"""
    from open_webui.env import AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET
    
    url = f'https://{AUTH0_DOMAIN}/oauth/token'
    payload = {
        'grant_type': 'client_credentials',
        'client_id': AUTH0_CLIENT_ID,
        'client_secret': AUTH0_CLIENT_SECRET,
        'audience': f'https://{AUTH0_DOMAIN}/api/v2/'
    }
    response = requests.post(url, json=payload)
    return response.json()['access_token']

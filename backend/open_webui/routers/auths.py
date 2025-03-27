import re
import uuid
import time
import datetime
import logging
from open_webui.internal.db import get_db
from open_webui.models.users import User, UserModel, Users
from aiohttp import ClientSession

from open_webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    Token,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    WEBUI_AUTH,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    WEBUI_NAME,
    DATA_DIR,
    SRC_LOG_LEVELS,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from open_webui.config import (
    OPENID_PROVIDER_URL,
    ENABLE_OAUTH_SIGNUP,
    AUTH0_CALLBACK_URL,
    AUTH0_CLIENT_ID,
    AUTH0_CLIENT_SECRET,
    AUTH0_DOMAIN,
    ENABLE_LDAP,
    DEFAULT_USER_PERMISSIONS
)
from pydantic import BaseModel
from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.utils.auth import (
    create_api_key,
    create_token,
    get_admin_user,
    get_verified_user,
    get_current_user,
    get_password_hash,
)
from open_webui.utils.webhook import post_webhook
from open_webui.utils.access_control import get_permissions

from typing import Optional, List

from ssl import CERT_REQUIRED, PROTOCOL_TLS

if ENABLE_LDAP.value:
    from ldap3 import Server, Connection, NONE, Tls
    from ldap3.utils.conv import escape_filter_chars

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# Helper function to ensure we get the most current DEFAULT_USER_ROLE value
def get_current_default_user_role(config):
    """
    Get the current DEFAULT_USER_ROLE from config, ensuring we have the most up-to-date value.
    Falls back to 'user' if there's any issue retrieving the value.
    """
    try:
        role = config.DEFAULT_USER_ROLE
        # Validate that the role is one of the acceptable values
        if role not in ["pending", "user", "admin"]:
            log.warning(f"Invalid DEFAULT_USER_ROLE value: {role}, falling back to 'user'")
            return "user"
        return role
    except Exception as e:
        log.error(f"Error retrieving DEFAULT_USER_ROLE: {e}")
        # Default to 'user' as a safe fallback
        return "user"

############################
# GetSessionUser
############################


class SessionUserResponse(Token, UserResponse):
    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request, response: Response, user=Depends(get_current_user)
):
    expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )

    datetime_expires_at = (
        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
        if expires_at
        else None
    )

    # Set the cookie token
    response.set_cookie(
        key="token",
        value=token,
        expires=datetime_expires_at,
        httponly=False,  # Allow JavaScript to access the cookie
        samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
        secure=WEBUI_AUTH_COOKIE_SECURE,
    )

    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
        "permissions": user_permissions,
    }


############################
# Update Profile
############################


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm, session_user=Depends(get_verified_user)
):
    if session_user:
        user = Users.update_user_by_id(
            session_user.id,
            {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Password
############################


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm, session_user=Depends(get_current_user)
):
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if session_user:
        user = Auths.authenticate_user(session_user.email, form_data.password)

        if user:
            hashed = get_password_hash(form_data.new_password)
            return Auths.update_user_password_by_id(user.id, hashed)
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_PASSWORD)
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# LDAP Authentication
############################
@router.post("/ldap", response_model=SessionUserResponse)
async def ldap_auth(request: Request, response: Response, form_data: LdapForm):
    ENABLE_LDAP = request.app.state.config.ENABLE_LDAP
    LDAP_SERVER_LABEL = request.app.state.config.LDAP_SERVER_LABEL
    LDAP_SERVER_HOST = request.app.state.config.LDAP_SERVER_HOST
    LDAP_SERVER_PORT = request.app.state.config.LDAP_SERVER_PORT
    LDAP_ATTRIBUTE_FOR_MAIL = request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL
    LDAP_ATTRIBUTE_FOR_USERNAME = request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME
    LDAP_SEARCH_BASE = request.app.state.config.LDAP_SEARCH_BASE
    LDAP_SEARCH_FILTERS = request.app.state.config.LDAP_SEARCH_FILTERS
    LDAP_APP_DN = request.app.state.config.LDAP_APP_DN
    LDAP_APP_PASSWORD = request.app.state.config.LDAP_APP_PASSWORD
    LDAP_USE_TLS = request.app.state.config.LDAP_USE_TLS
    LDAP_CA_CERT_FILE = request.app.state.config.LDAP_CA_CERT_FILE
    LDAP_CIPHERS = (
        request.app.state.config.LDAP_CIPHERS
        if request.app.state.config.LDAP_CIPHERS
        else "ALL"
    )

    if not ENABLE_LDAP:
        raise HTTPException(400, detail="LDAP authentication is not enabled")

    try:
        tls = Tls(
            validate=CERT_REQUIRED,
            version=PROTOCOL_TLS,
            ca_certs_file=LDAP_CA_CERT_FILE,
            ciphers=LDAP_CIPHERS,
        )
    except Exception as e:
        log.error(f"An error occurred on TLS: {str(e)}")
        raise HTTPException(400, detail=str(e))

    try:
        server = Server(
            host=LDAP_SERVER_HOST,
            port=LDAP_SERVER_PORT,
            get_info=NONE,
            use_ssl=LDAP_USE_TLS,
            tls=tls,
        )
        connection_app = Connection(
            server,
            LDAP_APP_DN,
            LDAP_APP_PASSWORD,
            auto_bind="NONE",
            authentication="SIMPLE",
        )
        if not connection_app.bind():
            raise HTTPException(400, detail="Application account bind failed")

        search_success = connection_app.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f"(&({LDAP_ATTRIBUTE_FOR_USERNAME}={escape_filter_chars(form_data.user.lower())}){LDAP_SEARCH_FILTERS})",
            attributes=[
                f"{LDAP_ATTRIBUTE_FOR_USERNAME}",
                f"{LDAP_ATTRIBUTE_FOR_MAIL}",
                "cn",
            ],
        )

        if not search_success:
            raise HTTPException(400, detail="User not found in the LDAP server")

        entry = connection_app.entries[0]
        username = str(entry[f"{LDAP_ATTRIBUTE_FOR_USERNAME}"]).lower()
        email = str(entry[f"{LDAP_ATTRIBUTE_FOR_MAIL}"])
        if not email or email == "" or email == "[]":
            raise HTTPException(400, f"User {form_data.user} does not have email.")
        else:
            email = email.lower()

        cn = str(entry["cn"])
        user_dn = entry.entry_dn

        if username == form_data.user.lower():
            connection_user = Connection(
                server,
                user_dn,
                form_data.password,
                auto_bind="NONE",
                authentication="SIMPLE",
            )
            if not connection_user.bind():
                raise HTTPException(400, f"Authentication failed for {form_data.user}")

            user = Users.get_user_by_email(email)
            if not user:
                try:
                    user_count = Users.get_num_users()

                    role = (
                        "admin"
                        if user_count == 0
                        else request.app.state.config.DEFAULT_USER_ROLE
                    )

                    user = Auths.insert_new_auth(
                        email=email,
                        password=str(uuid.uuid4()),
                        name=cn,
                        role=role,
                    )

                    if not user:
                        raise HTTPException(
                            500, detail=ERROR_MESSAGES.CREATE_USER_ERROR
                        )

                except HTTPException:
                    raise
                except Exception as err:
                    raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))

            user = Auths.authenticate_user_by_trusted_header(email)

            if user:
                token = create_token(
                    data={"id": user.id},
                    expires_delta=parse_duration(
                        request.app.state.config.JWT_EXPIRES_IN
                    ),
                )

                # Set the cookie token
                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=False,  # Allow JavaScript to access the cookie
                )

                user_permissions = get_permissions(
                    user.id, request.app.state.config.USER_PERMISSIONS
                )

                return {
                    "token": token,
                    "token_type": "Bearer",
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "profile_image_url": user.profile_image_url,
                    "permissions": user_permissions,
                }
            else:
                raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        else:
            raise HTTPException(
                400,
                f"User {form_data.user} does not match the record. Search result: {str(entry[f'{LDAP_ATTRIBUTE_FOR_USERNAME}'])}",
            )
    except Exception as e:
        raise HTTPException(400, detail=str(e))


############################
# Auth0 Authentication
############################

@router.get("/oauth/auth0/login")
async def auth0_login(request: Request, frontendOrigin: str = None, returnTo: str = None):
    """
    Redirect to Auth0 login page for authentication.
    """
    import logging
    from open_webui.utils.oauth import oauth_manager, initialize_oauth_manager
    import os
    
    logger = logging.getLogger("open_webui.auths")
    logger.info("Handling Auth0 login with correct callback URL")
    logger.info(f"Current environment AUTH0_CLIENT_ID: {os.environ.get('AUTH0_CLIENT_ID', 'None')}")
    logger.info(f"Current AUTH0_CLIENT_ID config value: {AUTH0_CLIENT_ID.value}")
    logger.info(f"Received frontend origin: {frontendOrigin}")
    logger.info(f"Received returnTo URL: {returnTo}")
    
    # Store the frontend origin and returnTo URL in the session for use during callback
    request.session["frontend_origin"] = frontendOrigin
    request.session["return_to"] = returnTo
    
    oauth_mgr = oauth_manager
    if oauth_mgr is None:
        logger.info("Initializing OAuth manager")
        oauth_mgr = initialize_oauth_manager()
    
    # Use the environment variable for the callback URL
    callback_url = AUTH0_CALLBACK_URL.value
    logger.info(f"Using callback URL from environment: {callback_url}")

    # Use the Auth0 client but with our specific callback URL
    client = oauth_mgr.get_client("auth0")
    return await client.authorize_redirect(
        request,
        redirect_uri=callback_url,
        prompt="login"  # Force Auth0 to show the login screen every time
    )


@router.get("/oauth/auth0")
async def login_auth0(request: Request):
    """
    Redirect to Auth0 login page
    """
    import logging
    from open_webui.utils.oauth import oauth_manager, initialize_oauth_manager
    
    logger = logging.getLogger("open_webui.auths")
    logger.info("Redirecting to Auth0 login page")
    
    oauth_mgr = oauth_manager
    if oauth_mgr is None:
        logger.info("Initializing OAuth manager")
        oauth_mgr = initialize_oauth_manager()
    
    try:
        return await oauth_mgr.login(request, "auth0")
    except Exception as e:
        logger.error(f"Error redirecting to Auth0: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error redirecting to Auth0: {str(e)}"
        )


# Helper functions for Auth0 callback
def handle_auth0_error(request, error, error_description):
    """Handle errors returned from Auth0"""
    from loguru import logger
    from urllib.parse import quote
    from starlette.responses import RedirectResponse
    
    logger.error(f"Auth0 returned an error: {error} - {error_description}")
    
    # Get frontend URL for redirect based on the frontend_origin in the session
    frontend_origin = request.session.get("frontend_origin", "")
    error_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
    
    # Ensure error_url doesn't end with a slash before adding query parameters
    if error_url.endswith('/'):
        error_url = error_url[:-1]
        
    # Create an error message and redirect to the frontend
    error_message = error_description or error or "An unknown error occurred during authentication"
    encoded_error = quote(error_message)
    
    logger.error(f"Redirecting to error page with: {error_message}")
    return RedirectResponse(url=f"{error_url}/auth?error={encoded_error}")

def get_frontend_url(request, result_data=None):
    """Standardize frontend URL construction"""
    # First try to get from result_data if provided
    if result_data and "frontend_base_url" in result_data:
        frontend_url = result_data.get("frontend_base_url", "")
        if frontend_url:
            # Ensure no trailing slash
            if frontend_url.endswith('/'):
                frontend_url = frontend_url[:-1]
            return frontend_url
    
    # Fall back to session or default construction
    frontend_origin = request.session.get("frontend_origin", "")
    if frontend_origin:
        if frontend_origin.endswith('/'):
            frontend_origin = frontend_origin[:-1]
        return frontend_origin
    
    # Last resort - construct from request base URL
    base_url = f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    
    return base_url

def extract_user_info(user_data):
    """Extract and normalize user information from Auth0 user data"""
    from loguru import logger
    
    user_info = {
        'email': user_data.get("email"),
        'id': user_data.get("sub"),  # The Auth0 user ID
        'name': user_data.get("name"),
        'picture': user_data.get("picture"),
        'phone_number': user_data.get("phone_number") if "phone_number" in user_data else None
    }
    
    # If name is not provided, use email or phone number
    if not user_info['name']:
        if user_info['email']:
            user_info['name'] = user_info['email']
        elif user_info['phone_number']:
            user_info['name'] = user_info['phone_number']
        else:
            # Last resort - create a name from user_id
            provider = user_info['id'].split('|')[0] if '|' in user_info['id'] else "unknown"
            user_sub = user_info['id'].split('|')[-1] if '|' in user_info['id'] else user_info['id']
            user_info['name'] = f"User_{provider}_{user_sub[:8]}"
    
    # Ensure we have a valid email (required by the database schema)
    if not user_info['email']:
        provider = user_info['id'].split('|')[0] if '|' in user_info['id'] else "unknown"
        if user_info['phone_number']:
            user_info['email'] = f"{user_info['phone_number']}@auth0user.com"
        else:
            user_sub = user_info['id'].split('|')[-1] if '|' in user_info['id'] else user_info['id']
            user_info['email'] = f"{provider}.{user_sub}@auth0user.com"
        logger.info(f"Created default email {user_info['email']} for user with ID {user_info['id']}")
    
    return user_info

def find_user_by_identifiers(db, user_info):
    """Find a user by OAuth ID, email, or phone number"""
    user = None
    
    # First try to find user by oauth_sub which is the most reliable identifier
    if user_info['id']:
        user = db.query(User).filter(User.oauth_sub == user_info['id']).first()
        
    # If not found by oauth_sub, try email
    if user is None and user_info['email']:
        user = db.query(User).filter(User.email == user_info['email']).first()
        
    # If still not found, try phone number
    if user is None and user_info['phone_number']:
        users = db.query(User).all()
        for u in users:
            if hasattr(u, 'info') and u.info and isinstance(u.info, dict):
                if u.info.get('phone_number') == user_info['phone_number']:
                    user = u
                    break
    
    return user

def has_sufficient_user_info(user_info):
    """Check if we have enough info to identify or create a user"""
    return bool(user_info['id'] or user_info['email'] or user_info['phone_number'])

def create_or_update_user(db, user, user_info):
    """Create a new user or update an existing one based on Auth0 data"""
    from loguru import logger
    import uuid
    import time
    
    if user is None:
        # User doesn't exist, create a new one
        user_uuid = str(uuid.uuid4())
        
        # Create the user with SQLAlchemy
        new_user = User(
            id=user_uuid,
            name=user_info['name'],
            email=user_info['email'],
            role="pending",
            profile_image_url=user_info['picture'] if user_info['picture'] else "/user.png",
            last_active_at=int(time.time()),
            created_at=int(time.time()),
            updated_at=int(time.time()),
            oauth_sub=user_info['id']
        )
        
        # Add the user to the database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Use the utility to add default permissions for the user
        try:
            from open_webui.utils.access_control import get_permissions
            from open_webui.config import DEFAULT_USER_PERMISSIONS
            # We don't need to do anything special here, as the get_permissions function
            # will automatically use the default permissions when the user first logs in
            logger.info(f"Default permissions for user {new_user.id} will be applied automatically")
        except Exception as e:
            logger.error(f"Error setting default permissions: {str(e)}")
        
        user = new_user
    else:
        # User exists, update if needed
        if user.oauth_sub != user_info['id']:
            user.oauth_sub = user_info['id']
        if user_info['email'] and not user.email:
            user.email = user_info['email']
        if user_info['name'] and not user.name:
            user.name = user_info['name']
        if user_info['picture'] and not user.profile_image_url:
            user.profile_image_url = user_info['picture']
        
        user.updated_at = int(time.time())
        user.last_active_at = int(time.time())
        
        # Update role if needed
        if hasattr(user, 'role') and user.role == "pending":
            # Update role to "user" if it was pending
            user.role = "user"
            
        db.commit()
    
    return user

def generate_auth_tokens(user):
    """Generate JWT tokens for authentication"""
    from open_webui.utils.auth import create_token
    
    return {
        'access_token': create_token(data={"id": str(user.id)}),
        'refresh_token': create_token(data={"id": str(user.id)})
    }

def prepare_auth_response(frontend_url, tokens):
    """Prepare the redirect response with authentication cookies"""
    from loguru import logger
    from starlette.responses import RedirectResponse
    
    # Prepare frontend URL with token in query params
    redirect_url = f"{frontend_url}/auth?token={tokens['access_token']}"
    logger.info(f"Redirecting to {redirect_url}")
    
    # Prepare cookies for the response
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        "access_token",
        tokens['access_token'],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    response.set_cookie(
        "refresh_token",
        tokens['refresh_token'],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    
    return response

def handle_missing_user_data(frontend_url):
    """Handle the case when no user data is returned from Auth0"""
    from loguru import logger
    from urllib.parse import quote
    from starlette.responses import RedirectResponse
    
    logger.error("No user data returned from Auth0")
    encoded_error = quote("Authentication failed: No user data returned from Auth0")
    return RedirectResponse(url=f"{frontend_url}/auth?error={encoded_error}")

def handle_insufficient_user_info(frontend_url):
    """Handle the case when insufficient user info is provided"""
    from loguru import logger
    from urllib.parse import quote
    from starlette.responses import RedirectResponse
    
    logger.error("No identifiable information found in Auth0 user data")
    encoded_error = quote("Authentication failed: No identifier provided by Auth0")
    return RedirectResponse(url=f"{frontend_url}/auth?error={encoded_error}")

def handle_general_exception(request, exception):
    """Handle general exceptions in the Auth0 callback process"""
    from loguru import logger
    from urllib.parse import quote
    from starlette.responses import RedirectResponse
    
    # Log the error
    logger.error(f"Error in Auth0 callback: {str(exception)}")
    logger.exception(exception)
    
    # Get frontend URL
    frontend_url = get_frontend_url(request)
    
    # Create an error message and redirect to the frontend
    encoded_error = quote(f"Authentication error: {str(exception)}")
    
    logger.error(f"Redirecting to error page with: {str(exception)}")
    return RedirectResponse(url=f"{frontend_url}/auth?error={encoded_error}")

@router.get("/oauth/auth0/callback")
async def auth0_callback(
    request: Request,
    response: Response,
    code: str = None,
    state: str = None,
    error: str = None,
    error_description: str = None,
):
    """ Auth0 callback endpoint """
    from loguru import logger
    from urllib.parse import quote
    from starlette.responses import RedirectResponse
    from open_webui.utils.auth import get_password_hash, create_token
    from open_webui.internal.db import SessionLocal
    
    # Check if we have error parameters from Auth0
    if error or error_description:
        return handle_auth0_error(request, error, error_description)
    
    try:
        # Get the OAuth manager
        from open_webui.utils.oauth import oauth_manager
        
        # Process the callback 
        result = await oauth_manager.handle_callback(request, "auth0", response)
        
        # Check if there was an error in the callback
        if result and result.get("error"):
            logger.error(f"Redirecting to error page with: {result.get('redirect_url')}")
            return RedirectResponse(url=result.get("redirect_url"))
        
        # Get user data from the result
        user_data = result.get("user_data", {})
        
        # Get frontend URL
        frontend_url = get_frontend_url(request, result)
        
        if not user_data:
            return handle_missing_user_data(frontend_url)
        
        # Extract and normalize user information
        user_info = extract_user_info(user_data)
        
        # Database operations in a single session
        db = SessionLocal()
        try:
            # Find user by identifiers
            user = find_user_by_identifiers(db, user_info)
            
            # Check if we have enough info to identify or create a user
            if user is None and not has_sufficient_user_info(user_info):
                return handle_insufficient_user_info(frontend_url)
            
            # Create or update user
            user = create_or_update_user(db, user, user_info)
            
            # Generate authentication tokens
            tokens = generate_auth_tokens(user)
            
            # Prepare and return response with cookies
            return prepare_auth_response(frontend_url, tokens)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in Auth0 callback database operations: {str(e)}")
            logger.exception(e)
            encoded_error = quote(f"Authentication failed: {str(e)}")
            return RedirectResponse(url=f"{frontend_url}/auth?error={encoded_error}")
        finally:
            db.close()
            
    except Exception as e:
        return handle_general_exception(request, e)


############################
# SignIn
############################


@router.post("/signin", response_model=SessionUserResponse)
async def signin(request: Request, response: Response, form_data: SigninForm):
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        if WEBUI_AUTH_TRUSTED_EMAIL_HEADER not in request.headers:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

        trusted_email = request.headers[WEBUI_AUTH_TRUSTED_EMAIL_HEADER].lower()
        trusted_name = trusted_email
        if WEBUI_AUTH_TRUSTED_NAME_HEADER:
            trusted_name = request.headers.get(
                WEBUI_AUTH_TRUSTED_NAME_HEADER, trusted_email
            )
        if not Users.get_user_by_email(trusted_email.lower()):
            await signup(
                request,
                response,
                SignupForm(
                    email=trusted_email, password=str(uuid.uuid4()), name=trusted_name
                ),
            )
        user = Auths.authenticate_user_by_trusted_header(trusted_email)
    elif WEBUI_AUTH == False:
        admin_email = "admin@localhost"
        admin_password = "admin"

        if Users.get_user_by_email(admin_email.lower()):
            user = Auths.authenticate_user(admin_email.lower(), admin_password)
        else:
            if Users.get_num_users() != 0:
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            await signup(
                request,
                response,
                SignupForm(email=admin_email, password=admin_password, name="User"),
            )

            user = Auths.authenticate_user(admin_email.lower(), admin_password)
    else:
        user = Auths.authenticate_user(form_data.email.lower(), form_data.password)

    if user:

        expires = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
        if expires is None:
            # Default to 30 days if no expiration is set
            expires = 30 * 24 * 60 * 60  # 30 days in seconds
        else:
            expires = int(expires.total_seconds())

        token = create_token(
            data={"id": user.id},
            expires_delta=datetime.timedelta(seconds=expires),
        )

        datetime_expires_at = (
            datetime.datetime.fromtimestamp(int(time.time()) + expires, datetime.timezone.utc)
            if expires
            else None
        )

        # Set the cookie token
        response.set_cookie(
            key="token",
            value=token,
            expires=datetime_expires_at,
            httponly=False,  # Allow JavaScript to access the cookie
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )

        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": int(time.time()) + expires,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# SignUp
############################


@router.post("/signup", response_model=SessionUserResponse)
async def signup(request: Request, response: Response, form_data: SignupForm):

    if WEBUI_AUTH:
        if (
            not request.app.state.config.ENABLE_SIGNUP
            or not request.app.state.config.ENABLE_LOGIN_FORM
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
    else:
        if Users.get_num_users() != 0:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )

    user_count = Users.get_num_users()
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        # Log the current DEFAULT_USER_ROLE setting before assigning it
        default_role = get_current_default_user_role(request.app.state.config)
        log.info(f"Current DEFAULT_USER_ROLE setting: {default_role}")

        role = (
            "admin" if user_count == 0 else default_role
        )
        
        log.info(f"Assigning role '{role}' to new user {form_data.email}")

        if user_count == 0:
            # Disable signup after the first user is created
            request.app.state.config.ENABLE_SIGNUP = False

        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            role,
        )

        if user:
            expires = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
            if expires is None:
                # Default to 30 days if no expiration is set
                expires = 30 * 24 * 60 * 60  # 30 days in seconds
            else:
                expires = int(expires.total_seconds())

            token = create_token(
                data={"id": user.id},
                expires_delta=datetime.timedelta(seconds=expires),
            )

            datetime_expires_at = (
                datetime.datetime.fromtimestamp(int(time.time()) + expires, datetime.timezone.utc)
                if expires
                else None
            )

            # Set the cookie token
            response.set_cookie(
                key="token",
                value=token,
                expires=datetime_expires_at,
                httponly=False,  # Allow JavaScript to access the cookie
                samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                secure=WEBUI_AUTH_COOKIE_SECURE,
            )

            if request.app.state.config.WEBHOOK_URL:
                post_webhook(
                    request.app.state.WEBUI_NAME,
                    request.app.state.config.WEBHOOK_URL,
                    WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                    {
                        "action": "signup",
                        "message": WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                        "user": user.model_dump_json(exclude_none=True),
                    },
                )

            user_permissions = get_permissions(
                user.id, request.app.state.config.USER_PERMISSIONS
            )

            return {
                "token": token,
                "token_type": "Bearer",
                "expires_at": int(time.time()) + expires,
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
                "permissions": user_permissions,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


@router.get("/signout")
async def signout(request: Request, response: Response):
    response.delete_cookie("token")

    if ENABLE_OAUTH_SIGNUP.value:
        oauth_id_token = request.cookies.get("oauth_id_token")
        if oauth_id_token:
            try:
                async with ClientSession() as session:
                    async with session.get(OPENID_PROVIDER_URL.value) as resp:
                        if resp.status == 200:
                            openid_data = await resp.json()
                            logout_url = openid_data.get("end_session_endpoint")
                            if logout_url:
                                response.delete_cookie("oauth_id_token")
                                return RedirectResponse(
                                    headers=response.headers,
                                    url=f"{logout_url}?id_token_hint={oauth_id_token}",
                                )
                        else:
                            raise HTTPException(
                                status_code=resp.status,
                                detail="Failed to fetch OpenID configuration",
                            )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    return {"status": True}


############################
# AddUser
############################


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        # If no specific role is provided, use our default role helper
        if not form_data.role or form_data.role not in ["pending", "user", "admin"]:
            form_data.role = get_current_default_user_role(user.request.app.state.config)
            log.info(f"Setting default role '{form_data.role}' for manually added user {form_data.email}")

        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            form_data.role,
        )

        if user:
            token = create_token(data={"id": user.id})
            return {
                "token": token,
                "token_type": "Bearer",
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


############################
# GetAdminDetails
############################


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_current_user)):
    if request.app.state.config.SHOW_ADMIN_DETAILS:
        admin_email = request.app.state.config.ADMIN_EMAIL
        admin_name = None

        log.info(f"Admin details - Email: {admin_email}, Name: {admin_name}")

        if admin_email:
            admin = Users.get_user_by_email(admin_email)
            if admin:
                admin_name = admin.name
        else:
            admin = Users.get_first_user()
            if admin:
                admin_email = admin.email
                admin_name = admin.name

        return {
            "name": admin_name,
            "email": admin_email,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)


############################
# ToggleSignUp
############################


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    return {
        "SHOW_ADMIN_DETAILS": request.app.state.config.SHOW_ADMIN_DETAILS,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "ENABLE_API_KEY": request.app.state.config.ENABLE_API_KEY,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
        "API_KEY_ALLOWED_ENDPOINTS": request.app.state.config.API_KEY_ALLOWED_ENDPOINTS,
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
    }


class AdminConfig(BaseModel):
    SHOW_ADMIN_DETAILS: bool
    WEBUI_URL: str
    ENABLE_SIGNUP: bool
    ENABLE_API_KEY: bool
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS: bool
    API_KEY_ALLOWED_ENDPOINTS: str
    ENABLE_CHANNELS: bool
    DEFAULT_USER_ROLE: str
    JWT_EXPIRES_IN: str
    ENABLE_COMMUNITY_SHARING: bool
    ENABLE_MESSAGE_RATING: bool


@router.post("/admin/config")
async def update_admin_config(
    request: Request, form_data: AdminConfig, user=Depends(get_admin_user)
):
    request.app.state.config.SHOW_ADMIN_DETAILS = form_data.SHOW_ADMIN_DETAILS
    request.app.state.config.WEBUI_URL = form_data.WEBUI_URL
    request.app.state.config.ENABLE_SIGNUP = form_data.ENABLE_SIGNUP

    request.app.state.config.ENABLE_API_KEY = form_data.ENABLE_API_KEY
    request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
        form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
    )
    request.app.state.config.API_KEY_ALLOWED_ENDPOINTS = (
        form_data.API_KEY_ALLOWED_ENDPOINTS
    )

    request.app.state.config.ENABLE_CHANNELS = form_data.ENABLE_CHANNELS

    if form_data.DEFAULT_USER_ROLE in ["pending", "user", "admin"]:
        request.app.state.config.DEFAULT_USER_ROLE = form_data.DEFAULT_USER_ROLE

    pattern = r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$"

    # Check if the input string matches the pattern
    if re.match(pattern, form_data.JWT_EXPIRES_IN):
        request.app.state.config.JWT_EXPIRES_IN = form_data.JWT_EXPIRES_IN

    request.app.state.config.ENABLE_COMMUNITY_SHARING = (
        form_data.ENABLE_COMMUNITY_SHARING
    )
    request.app.state.config.ENABLE_MESSAGE_RATING = form_data.ENABLE_MESSAGE_RATING

    return {
        "SHOW_ADMIN_DETAILS": request.app.state.config.SHOW_ADMIN_DETAILS,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "ENABLE_API_KEY": request.app.state.config.ENABLE_API_KEY,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": request.app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
        "API_KEY_ALLOWED_ENDPOINTS": request.app.state.config.API_KEY_ALLOWED_ENDPOINTS,
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
    }


class LdapServerConfig(BaseModel):
    label: str
    host: str
    port: Optional[int] = None
    attribute_for_mail: str = "mail"
    attribute_for_username: str = "uid"
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ""
    use_tls: bool = True
    certificate_path: Optional[str] = None
    ciphers: Optional[str] = "ALL"


@router.get("/admin/config/ldap/server", response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_mail": request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.post("/admin/config/ldap/server")
async def update_ldap_server(
    request: Request, form_data: LdapServerConfig, user=Depends(get_admin_user)
):
    required_fields = [
        "label",
        "host",
        "attribute_for_mail",
        "attribute_for_username",
        "app_dn",
        "app_dn_password",
        "search_base",
    ]
    for key in required_fields:
        value = getattr(form_data, key)
        if not value:
            raise HTTPException(400, detail=f"Required field {key} is empty")

    if form_data.use_tls and not form_data.certificate_path:
        raise HTTPException(
            400, detail="TLS is enabled but certificate file path is missing"
        )

    request.app.state.config.LDAP_SERVER_LABEL = form_data.label
    request.app.state.config.LDAP_SERVER_HOST = form_data.host
    request.app.state.config.LDAP_SERVER_PORT = form_data.port
    request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL = form_data.attribute_for_mail
    request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = (
        form_data.attribute_for_username
    )
    request.app.state.config.LDAP_APP_DN = form_data.app_dn
    request.app.state.config.LDAP_APP_PASSWORD = form_data.app_dn_password
    request.app.state.config.LDAP_SEARCH_BASE = form_data.search_base
    request.app.state.config.LDAP_SEARCH_FILTERS = form_data.search_filters
    request.app.state.config.LDAP_USE_TLS = form_data.use_tls
    request.app.state.config.LDAP_CA_CERT_FILE = form_data.certificate_path
    request.app.state.config.LDAP_CIPHERS = form_data.ciphers

    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_mail": request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.get("/admin/config/ldap")
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


class LdapConfigForm(BaseModel):
    enable_ldap: Optional[bool] = None


@router.post("/admin/config/ldap")
async def update_ldap_config(
    request: Request, form_data: LdapConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.ENABLE_LDAP = form_data.enable_ldap
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


############################
# API Key
############################


# create api key
@router.post("/api_key", response_model=ApiKey)
async def generate_api_key(request: Request, user=Depends(get_current_user)):
    if not request.app.state.config.ENABLE_API_KEY:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )

    api_key = create_api_key()
    success = Users.update_user_api_key_by_id(user.id, api_key)

    if success:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)


# delete api key
@router.delete("/api_key", response_model=bool)
async def delete_api_key(user=Depends(get_current_user)):
    success = Users.update_user_api_key_by_id(user.id, None)
    return success


# get api key
@router.get("/api_key", response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user)):
    api_key = Users.get_user_api_key_by_id(user.id)
    if api_key:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)

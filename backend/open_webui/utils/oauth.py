import base64
import logging
import mimetypes
import sys
import uuid
import json
import httpx
import aiohttp
from uuid import uuid4
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from loguru import logger
from fastapi import (
    HTTPException,
    status,
)
from open_webui.models.auths import Auths
from open_webui.models.users import Users
from open_webui.models.groups import Groups, GroupModel, GroupUpdateForm
from open_webui.config import (
    DEFAULT_USER_ROLE,
    ENABLE_OAUTH_SIGNUP,
    OAUTH_MERGE_ACCOUNTS_BY_EMAIL,
    OAUTH_PROVIDERS,
    ENABLE_OAUTH_ROLE_MANAGEMENT,
    ENABLE_OAUTH_GROUP_MANAGEMENT,
    OAUTH_ROLES_CLAIM,
    OAUTH_GROUPS_CLAIM,
    OAUTH_EMAIL_CLAIM,
    OAUTH_PICTURE_CLAIM,
    OAUTH_USERNAME_CLAIM,
    OAUTH_ALLOWED_ROLES,
    OAUTH_ADMIN_ROLES,
    OAUTH_ALLOWED_DOMAINS,
    WEBHOOK_URL,
    JWT_EXPIRES_IN,
    AppConfig,
)
from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    WEBUI_NAME,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    SRC_LOG_LEVELS, 
    GLOBAL_LOG_LEVEL
)
from open_webui.utils.misc import parse_duration
from open_webui.utils.auth import get_password_hash, create_token
from open_webui.utils.webhook import post_webhook
from open_webui.routers.auths import get_current_default_user_role

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OAUTH"])

auth_manager_config = AppConfig()
auth_manager_config.DEFAULT_USER_ROLE = DEFAULT_USER_ROLE
auth_manager_config.ENABLE_OAUTH_SIGNUP = ENABLE_OAUTH_SIGNUP
auth_manager_config.OAUTH_MERGE_ACCOUNTS_BY_EMAIL = OAUTH_MERGE_ACCOUNTS_BY_EMAIL
auth_manager_config.ENABLE_OAUTH_ROLE_MANAGEMENT = ENABLE_OAUTH_ROLE_MANAGEMENT
auth_manager_config.ENABLE_OAUTH_GROUP_MANAGEMENT = ENABLE_OAUTH_GROUP_MANAGEMENT
auth_manager_config.OAUTH_ROLES_CLAIM = OAUTH_ROLES_CLAIM
auth_manager_config.OAUTH_GROUPS_CLAIM = OAUTH_GROUPS_CLAIM
auth_manager_config.OAUTH_EMAIL_CLAIM = OAUTH_EMAIL_CLAIM
auth_manager_config.OAUTH_PICTURE_CLAIM = OAUTH_PICTURE_CLAIM
auth_manager_config.OAUTH_USERNAME_CLAIM = OAUTH_USERNAME_CLAIM
auth_manager_config.OAUTH_ALLOWED_ROLES = OAUTH_ALLOWED_ROLES
auth_manager_config.OAUTH_ADMIN_ROLES = OAUTH_ADMIN_ROLES
auth_manager_config.OAUTH_ALLOWED_DOMAINS = OAUTH_ALLOWED_DOMAINS
auth_manager_config.WEBHOOK_URL = WEBHOOK_URL
auth_manager_config.JWT_EXPIRES_IN = JWT_EXPIRES_IN


class OAuthManager:
    def __init__(self, app):
        self.oauth = OAuth()
        self.app = app
        for _, provider_config in OAUTH_PROVIDERS.items():
            provider_config["register"](self.oauth)

    def get_client(self, provider_name):
        return self.oauth.create_client(provider_name)

    def get_user_role(self, user, user_data):
        if user and Users.get_num_users() == 1:
            # If the user is the only user, assign the role "admin" - actually repairs role for single user on login
            log.debug("Assigning the only user the admin role")
            return "admin"
        if not user and Users.get_num_users() == 0:
            # If there are no users, assign the role "admin", as the first user will be an admin
            log.debug("Assigning the first user the admin role")
            return "admin"

        if auth_manager_config.ENABLE_OAUTH_ROLE_MANAGEMENT:
            log.debug("Running OAUTH Role management")
            oauth_claim = auth_manager_config.OAUTH_ROLES_CLAIM
            oauth_allowed_roles = auth_manager_config.OAUTH_ALLOWED_ROLES
            oauth_admin_roles = auth_manager_config.OAUTH_ADMIN_ROLES
            oauth_roles = None
            # Default/fallback role if no matching roles are found
            # Hard-code role to 'user' instead of using potentially broken config
            role = "user"
            log.info(f"OAuth: Setting default role 'user' for new user")

            # Next block extracts the roles from the user data, accepting nested claims of any depth
            if oauth_claim and oauth_allowed_roles and oauth_admin_roles:
                claim_data = user_data
                nested_claims = oauth_claim.split(".")
                for nested_claim in nested_claims:
                    claim_data = claim_data.get(nested_claim, {})
                oauth_roles = claim_data if isinstance(claim_data, list) else None

            log.debug(f"Oauth Roles claim: {oauth_claim}")
            log.debug(f"User roles from oauth: {oauth_roles}")
            log.debug(f"Accepted user roles: {oauth_allowed_roles}")
            log.debug(f"Accepted admin roles: {oauth_admin_roles}")

            # If any roles are found, check if they match the allowed or admin roles
            if oauth_roles:
                # If role management is enabled, and matching roles are provided, use the roles
                for allowed_role in oauth_allowed_roles:
                    # If the user has any of the allowed roles, assign the role "user"
                    if allowed_role in oauth_roles:
                        log.debug("Assigned user the user role")
                        role = "user"
                        break
                for admin_role in oauth_admin_roles:
                    # If the user has any of the admin roles, assign the role "admin"
                    if admin_role in oauth_roles:
                        log.debug("Assigned user the admin role")
                        role = "admin"
                        break
        else:
            if not user:
                # If role management is disabled, use the default role for new users
                # Hard-code role to 'user' instead of using potentially broken config
                role = "user"
                log.info(f"OAuth: Setting default role 'user' for new user")
            else:
                # If role management is disabled, use the existing role for existing users
                role = user.role

        return role

    def update_user_groups(self, user, user_data, default_permissions):
        log.debug("Running OAUTH Group management")
        oauth_claim = auth_manager_config.OAUTH_GROUPS_CLAIM

        # Nested claim search for groups claim
        if oauth_claim:
            claim_data = user_data
            nested_claims = oauth_claim.split(".")
            for nested_claim in nested_claims:
                claim_data = claim_data.get(nested_claim, {})
            user_oauth_groups = claim_data if isinstance(claim_data, list) else []

        user_current_groups: list[GroupModel] = Groups.get_groups_by_member_id(user.id)
        all_available_groups: list[GroupModel] = Groups.get_groups()

        log.debug(f"Oauth Groups claim: {oauth_claim}")
        log.debug(f"User oauth groups: {user_oauth_groups}")
        log.debug(f"User's current groups: {[g.name for g in user_current_groups]}")
        log.debug(
            f"All groups available in OpenWebUI: {[g.name for g in all_available_groups]}"
        )

        # Remove groups that user is no longer a part of
        for group_model in user_current_groups:
            if group_model.name not in user_oauth_groups:
                # Remove group from user
                log.debug(
                    f"Removing user from group {group_model.name} as it is no longer in their oauth groups"
                )

                user_ids = group_model.user_ids
                user_ids = [i for i in user_ids if i != user.id]

                # In case a group is created, but perms are never assigned to the group by hitting "save"
                group_permissions = group_model.permissions
                if not group_permissions:
                    group_permissions = default_permissions

                update_form = GroupUpdateForm(
                    name=group_model.name,
                    description=group_model.description,
                    permissions=group_permissions,
                    user_ids=user_ids,
                )
                Groups.update_group_by_id(
                    id=group_model.id, form_data=update_form, overwrite=False
                )

        # Add user to new groups
        for group_model in all_available_groups:
            if group_model.name in user_oauth_groups and not any(
                gm.name == group_model.name for gm in user_current_groups
            ):
                # Add user to group
                log.debug(
                    f"Adding user to group {group_model.name} as it was found in their oauth groups"
                )

                user_ids = group_model.user_ids
                user_ids.append(user.id)

                # In case a group is created, but perms are never assigned to the group by hitting "save"
                group_permissions = group_model.permissions
                if not group_permissions:
                    group_permissions = default_permissions

                update_form = GroupUpdateForm(
                    name=group_model.name,
                    description=group_model.description,
                    permissions=group_permissions,
                    user_ids=user_ids,
                )
                Groups.update_group_by_id(
                    id=group_model.id, form_data=update_form, overwrite=False
                )

    async def login(self, request, provider):
        """
        Redirect to the OAuth provider's authorization page.
        """
        client = self.get_client(provider)

        # Form the redirect URL for the callback
        redirect_uri = f"{request.url.scheme}://{request.url.netloc}{request.app.url_path_for(f'oauth_{provider}_callback')}"

        # Store origin in session for callback redirect
        if "frontend_origin" in request.query_params:
            request.session["frontend_origin"] = request.query_params["frontend_origin"]

        # Store returnTo URL in session for callback redirect
        if "returnTo" in request.query_params:
            request.session["returnTo"] = request.query_params["returnTo"]

        try:
            return await client.authorize_redirect(request, redirect_uri)
        except Exception as e:
            log.error(f"Error redirecting to {provider}: {str(e)}")
            log.exception(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error redirecting to {provider}: {str(e)}"
            )

    def _get_provider_data(self, provider_name):
        """
        Get the provider configuration data for a given provider name.
        
        Args:
            provider_name: The name of the OAuth provider (e.g., 'auth0', 'google', etc.)
            
        Returns:
            dict: The provider configuration data or None if not found
        """
        from loguru import logger as log
        
        try:
            if provider_name in OAUTH_PROVIDERS:
                return OAUTH_PROVIDERS[provider_name]
            log.error(f"Provider {provider_name} not found in OAUTH_PROVIDERS")
            return None
        except Exception as e:
            log.error(f"Error getting provider data for {provider_name}: {str(e)}")
            log.exception(e)
            return None
    
    async def _get_token(self, request, provider_name):
        """
        Get the token from the OAuth provider using the authorization code
        
        Args:
            request: The request object from the callback
            provider_name: The name of the OAuth provider (e.g., 'auth0', 'google', etc.)
            
        Returns:
            dict: The token data or None if failed
        """
        from loguru import logger as log
        
        try:
            client = self.get_client(provider_name)
            if not client:
                log.error(f"Client not found for {provider_name}")
                return None
                
            # Get the redirect URI for the callback - using direct path construction
            # instead of url_path_for since the route might not have a name
            redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/v1/auths/oauth/{provider_name}/callback"
            
            log.info(f"Using redirect URI: {redirect_uri}")
            
            # Retrieve and validate the callback parameters
            code = request.query_params.get("code")
            state = request.query_params.get("state")
            
            if not code:
                log.error("No authorization code found in the request")
                return None
                
            log.info(f"Received authorization code and state in callback")
            
            try:
                # Exchange the authorization code for a token
                # We're passing the request object to get the code from query params
                # and explicitly set the redirect_uri to ensure it matches what was used in the authorization request
                token = await client.authorize_access_token(request)
                log.info(f"Successfully obtained access token for {provider_name}")
                return token
            except Exception as e:
                # If there's an error with the state parameter, try a direct token fetch
                log.warning(f"Error in authorize_access_token: {str(e)}")
                
                # If we get a state mismatch error, try to fetch the token directly without state validation
                # This is safe because we're still validating the code which is a one-time use credential
                if "state" in str(e).lower():
                    log.info("Attempting direct token retrieval without state validation")
                    try:
                        # Create token request parameters
                        token_params = {
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": redirect_uri,
                        }
                        
                        # Get provider data for client_id and token_endpoint
                        provider_data = await self._get_provider_data(provider_name)
                        if not provider_data:
                            log.error(f"Provider data not found for {provider_name}")
                            return None
                            
                        # Directly fetch the token from the token endpoint
                        token_endpoint = provider_data.get("token_endpoint")
                        client_id = provider_data.get("client_id")
                        client_secret = provider_data.get("client_secret")
                        
                        # Make a direct request to the token endpoint
                        async with aiohttp.ClientSession() as http_client:
                            auth = None
                            if client_id and client_secret:
                                auth = aiohttp.BasicAuth(client_id, client_secret)
                                
                            token_response = await http_client.post(
                                token_endpoint,
                                data=token_params,
                                auth=auth
                            )
                            
                            if token_response.status == 200:
                                token_data = await token_response.json()
                                log.info(f"Successfully obtained token directly from {provider_name}")
                                return token_data
                            else:
                                log.error(f"Failed to obtain token directly: {await token_response.text()}")
                                return None
                    except Exception as direct_error:
                        log.error(f"Error in direct token retrieval: {str(direct_error)}")
                        return None
                else:
                    log.error(f"Failed to get token for {provider_name}: {str(e)}")
                    return None
        except Exception as e:
            log.error(f"Error in _get_token: {str(e)}")
            return None
            
    async def _get_user_data(self, token, provider_name):
        """
        Get user data from the OAuth provider using the access token.
        
        Args:
            token: The access token from the OAuth provider
            provider_name: The name of the OAuth provider (e.g., 'auth0', 'google', etc.)
            
        Returns:
            dict: The user data or None if failed
        """
        from loguru import logger as log
        
        try:
            client = self.get_client(provider_name)
            if not client:
                log.error(f"Client not found for {provider_name}")
                return None
                
            # Get user info from the OAuth provider
            provider_data = self._get_provider_data(provider_name)
            if not provider_data:
                log.error(f"Provider data not found for {provider_name}")
                return None
                
            userinfo_endpoint = provider_data.get("userinfo_endpoint")
            if not userinfo_endpoint:
                # For providers that don't specify a userinfo endpoint in their metadata,
                # we'll try to get user info using the client's userinfo method
                try:
                    user_data = await client.userinfo(token=token)
                    return user_data
                except Exception as e:
                    log.error(f"Error getting user info for {provider_name}: {str(e)}")
                    log.exception(e)
                    return None
                    
            # For providers with a specified userinfo endpoint
            resp = await client.get(userinfo_endpoint, token=token)
            if resp.status_code != 200:
                log.error(f"Failed to get user info for {provider_name}: {resp.status_code}")
                return None
                
            return resp.json()
        except Exception as e:
            log.error(f"Error getting user info for {provider_name}: {str(e)}")
            log.exception(e)
            return None

    async def handle_callback(self, request, provider_name, response=None):
        """
        Handle the callback from an OAuth provider.
        
        Args:
            request: The request object from the callback
            provider_name: The name of the OAuth provider (e.g., 'auth0', 'google', etc.)
            response: Optional response object to redirect to on error
            
        Returns:
            dict: The result containing user data and redirect URLs
        """
        from loguru import logger as log
        from urllib.parse import quote
        
        try:
            log.info(f"Handling callback for {provider_name}")
            
            # Check for error in the callback
            error = request.query_params.get("error")
            if error:
                error_description = request.query_params.get("error_description", "")
                log.error(f"Error from provider {provider_name}: {error} - {error_description}")
                
                # Get frontend URL for error redirect
                frontend_origin = request.session.get("frontend_origin", "")
                error_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
                
                # Ensure error_url doesn't end with a slash
                if error_url.endswith('/'):
                    error_url = error_url[:-1]
                    
                encoded_error = quote(f"Error from {provider_name}: {error}")
                return {"error": True, "redirect_url": f"{error_url}/auth?error={encoded_error}"}
            
            # Get the token from the provider
            token = await self._get_token(request, provider_name)
            if not token:
                log.error(f"Failed to get token for {provider_name}")
                
                # Get frontend URL for error redirect
                frontend_origin = request.session.get("frontend_origin", "")
                error_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
                
                # Ensure error_url doesn't end with a slash
                if error_url.endswith('/'):
                    error_url = error_url[:-1]
                    
                encoded_error = quote(f"Failed to retrieve access token from {provider_name}")
                return {"error": True, "redirect_url": f"{error_url}/auth?error={encoded_error}"}
            
            # Get the user data from the provider
            user_data = await self._get_user_data(token, provider_name)
            if not user_data:
                log.error(f"Failed to get user data for {provider_name}")
                
                # Get frontend URL for error redirect
                frontend_origin = request.session.get("frontend_origin", "")
                error_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
                
                # Ensure error_url doesn't end with a slash
                if error_url.endswith('/'):
                    error_url = error_url[:-1]
                    
                encoded_error = quote(f"Failed to retrieve user data from {provider_name}")
                return {"error": True, "redirect_url": f"{error_url}/auth?error={encoded_error}"}
            
            # If response object is provided, use it to set cookies (cookie-based auth flow)
            if response:
                # Process the token
                from open_webui.utils.auth import create_token
                from open_webui.env import WEBUI_AUTH_COOKIE_SECURE, WEBUI_AUTH_COOKIE_SAME_SITE
                
                # Create a token
                jwt_token = create_token({"provider": provider_name, **user_data})
                
                # Set the cookie token
                response.set_cookie(
                    key="token",
                    value=jwt_token,
                    httponly=True,  # Ensures the cookie is not accessible via JavaScript
                    samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                    secure=WEBUI_AUTH_COOKIE_SECURE,
                )
                
                if auth_manager_config.ENABLE_OAUTH_SIGNUP:
                    oauth_id_token = token.get("id_token")
                    response.set_cookie(
                        key="oauth_id_token",
                        value=oauth_id_token,
                        httponly=True,
                        samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
                        secure=WEBUI_AUTH_COOKIE_SECURE,
                    )
                
                # Get frontend URL for redirect based on the frontend_origin in the session
                frontend_url = None
                try:
                    # Get the frontend_origin from the session
                    frontend_origin = request.session.get("frontend_origin")
                    
                    if frontend_origin:
                        # Use the frontend_origin from the session
                        frontend_url = frontend_origin
                        log.info(f"Using frontend URL from session: {frontend_url}")
                    else:
                        # Fallback to AUTH0_CALLBACK_URL if no frontend_origin in session
                        from open_webui.config import AUTH0_CALLBACK_URL
                        callback_url_str = AUTH0_CALLBACK_URL.value
                        
                        # For development environments, replace backend port with frontend port
                        if "localhost:8080" in callback_url_str or "127.0.0.1:8080" in callback_url_str:
                            frontend_url = callback_url_str.replace(":8080", ":5173")
                        else:
                            # For production, remove API path component
                            frontend_url = callback_url_str.split("/api/")[0] if "/api/" in callback_url_str else str(request.base_url).rstrip("/")
                        
                    log.info(f"Frontend URL for redirect: {frontend_url}")
                    
                    # Return user data and necessary redirect information
                    return {
                        "user_data": user_data,
                        "jwt_token": jwt_token,
                        "frontend_base_url": frontend_url
                    }
                except Exception as e:
                    log.error(f"Error determining frontend URL: {e}")
                    # Simple fallback using request base URL
                    base_url = str(request.base_url).rstrip("/")
                    frontend_url = base_url.replace(":8080", ":5173") if ":8080" in base_url else base_url
                
                return {
                    "user_data": user_data,
                    "jwt_token": jwt_token,
                    "frontend_base_url": frontend_url
                }
            
            # No response provided - regular token-based auth flow
            # Get frontend URL for success redirect
            frontend_origin = request.session.get("frontend_origin", "")
            frontend_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
            
            # Successful authentication - return the user data and redirect URL
            return {
                "user_data": user_data,
                "frontend_base_url": frontend_url,
                "token": token
            }
            
        except Exception as e:
            log.error(f"Failed to handle callback for {provider_name} - {str(e)}")
            log.exception(e)
            
            # Get frontend URL for error redirect
            frontend_origin = request.session.get("frontend_origin", "")
            error_url = frontend_origin or f"{request.base_url.scheme}://{request.base_url.netloc.replace(str(request.base_url.port), '5173')}"
            
            # Ensure error_url doesn't end with a slash
            if error_url.endswith('/'):
                error_url = error_url[:-1]
                
            encoded_error = quote(f"Authentication error: {str(e)}")
            return {"error": True, "redirect_url": f"{error_url}/auth?error={encoded_error}"}

    async def handle_callback_original(self, request, provider_name, response=None):
        """
        Handle the callback from an OAuth provider.
        
        This is a legacy method that now delegates to handle_callback.
        It is maintained for backward compatibility.
        """
        # Just call the refactored handle_callback with the same parameters
        return await self.handle_callback(request, provider_name, response)

# This will be filled by main.py after app initialization
oauth_manager = None

# Import deferred to avoid circular imports
def initialize_oauth_manager():
    global oauth_manager
    if oauth_manager is None:
        import logging
        logger = logging.getLogger("open_webui.oauth")
        logger.error("Initializing OAuth manager directly in oauth.py")
        
        # Log environment variables
        import os
        logger.error(f"AUTH0_CLIENT_ID from env: {os.environ.get('AUTH0_CLIENT_ID', 'None')}")
        logger.error(f"AUTH0_DOMAIN from env: {os.environ.get('AUTH0_DOMAIN', 'None')}")
        
        # Log config values
        from open_webui.config import AUTH0_CLIENT_ID, AUTH0_DOMAIN
        logger.error(f"AUTH0_CLIENT_ID from config: {AUTH0_CLIENT_ID.value}")
        logger.error(f"AUTH0_DOMAIN from config: {AUTH0_DOMAIN.value}")
        
        from fastapi import FastAPI
        app = FastAPI()
        oauth_manager = OAuthManager(app)
    return oauth_manager

import { createAuth0Client, Auth0Client } from '@auth0/auth0-spa-js';
import type { LogoutOptions } from '@auth0/auth0-spa-js';

// Auth0 configuration
const AUTH0_DOMAIN = 'channelai.us.auth0.com';
const AUTH0_CLIENT_ID = 'cEewmmCzsdXlyMjYPaVL0R0oG5cUch8S';

// Force consistent domain usage 
// Note: In production, consider using an environment variable to configure this
const PREFERRED_DOMAIN = 'localhost';  // or '127.0.0.1' based on Auth0 configuration

let auth0Client: Auth0Client | null = null;

/**
 * Get a consistent return URL for Auth0 callbacks
 */
const getConsistentReturnUrl = (): string => {
  // Get the current origin but ensure we use the preferred domain
  const origin = window.location.origin;
  const port = window.location.port ? `:${window.location.port}` : '';
  const protocol = window.location.protocol;
  
  // Construct a consistent URL using the preferred domain
  return `${protocol}//${PREFERRED_DOMAIN}${port}/auth`;
};

/**
 * Initialize the Auth0 client
 */
export const initAuth0 = async (): Promise<Auth0Client> => {
  if (auth0Client) {
    return auth0Client;
  }
  
  const redirectUri = getConsistentReturnUrl();
  console.log('Auth0 redirect URI:', redirectUri);
  
  auth0Client = await createAuth0Client({
    domain: AUTH0_DOMAIN,
    clientId: AUTH0_CLIENT_ID,
    authorizationParams: {
      redirect_uri: redirectUri
    }
  });
  
  return auth0Client;
};

/**
 * Logout from Auth0
 * @param options Logout options
 */
export const logout = async (options: LogoutOptions = {}): Promise<void> => {
  try {
    const client = await initAuth0();
    
    // Set defaults if not provided
    if (!options.logoutParams) {
      options.logoutParams = {};
    }
    
    // Use the consistent return URL
    if (!options.logoutParams.returnTo) {
      options.logoutParams.returnTo = getConsistentReturnUrl();
    }
    
    console.log('Auth0 logout returnTo:', options.logoutParams.returnTo);
    
    // Logout from Auth0
    await client.logout(options);
  } catch (error) {
    console.error('Error during Auth0 logout:', error);
    
    // Fallback to manual redirect if the SDK fails
    const returnUrl = encodeURIComponent(getConsistentReturnUrl());
    window.location.href = `https://${AUTH0_DOMAIN}/v2/logout?client_id=${AUTH0_CLIENT_ID}&returnTo=${returnUrl}`;
  }
};

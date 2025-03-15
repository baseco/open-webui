import { ampli } from '../../../ampli';
import { Types } from '@amplitude/analytics-browser';

/**
 * Initialize analytics with Ampli
 * @returns true if initialization was successful
 */
export function initializeAnalytics(): boolean {
  try {
    ampli.load({
      environment: 'nexus',
      // Enable debug mode in development
      client: {
        configuration: {
          logLevel: import.meta.env.DEV ? Types.LogLevel.Debug : Types.LogLevel.Error
        }
      }
    });
    
    console.log('Amplitude Analytics initialized successfully');
    return true;
  } catch (error) {
    console.error('Failed to initialize Amplitude Analytics:', error);
    return false;
  }
}

/**
 * Track user registration with Auth0
 * @param userId User ID
 */
export function trackUserRegisteredWithAuth0(userId: string): void {
  if (!userId) {
    console.warn('Cannot track user registration: Missing user ID');
    return;
  }
  
  // Set user ID for all subsequent events
  ampli.identify(userId, {
    "Signup Time": new Date().toISOString()
  });
  
  // Track registration event
  ampli.userRegisteredWithAuth0();
}

/**
 * Track user login with Auth0
 * @param userId User ID
 */
export function trackUserLoggedInWithAuth0(userId: string): void {
  if (!userId) {
    console.warn('Cannot track user login: Missing user ID');
    return;
  }
  
  // Set user ID for all subsequent events
  ampli.identify(userId, {
    "Last Login Time": new Date().toISOString()
  });
  
  // Track login event
  ampli.userLoggedInWithAuth0();
}

/**
 * Track user logout
 * @param userId User ID
 */
export function trackUserLoggedOut(userId: string): void {
  if (!userId) {
    console.warn('Cannot track user logout: Missing user ID');
    return;
  }
  
  // Track logout event before clearing user identity
  ampli.userLoggedOut();
}

/**
 * Add any new analytics tracking methods below...
 */

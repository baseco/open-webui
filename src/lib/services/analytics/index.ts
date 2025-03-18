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
 * Track conversation started
 * @param conversationId Conversation ID
 * @param modelIds List of model IDs used in the conversation
 */
export function trackConversationStarted(
  conversationId: string,
  modelIds: string[],
): void {
  if (!conversationId) {
    console.warn('Cannot track conversation start: Missing conversation ID');
    return;
  }
  
  if (!modelIds || modelIds.length === 0) {
    console.warn('Cannot track conversation start: Missing model IDs');
    return;
  }
  
  // Track conversation started event
  ampli.conversationStarted({
    conversationId,
    isMultiModel: modelIds.length > 1 ? 'true' : 'false',
    modelIdList: modelIds,
    primaryModelId: modelIds[0]
  });
}

/**
 * Track message sent
 * @param conversationId Conversation ID
 * @param messageId Message ID
 * @param messageContent Message content
 * @param modelIds List of model IDs used for the message
 */
export function trackMessageSent(
  conversationId: string,
  messageId: string,
  messageContent: string,
  modelIds?: string[]
): void {
  if (!conversationId) {
    console.warn('Cannot track message sent: Missing conversation ID');
    return;
  }
  
  if (!messageId) {
    console.warn('Cannot track message sent: Missing message ID');
    return;
  }
  
  // Ensure modelIds is at least an empty array
  const models = modelIds && modelIds.length > 0 ? modelIds : [];
  
  // Track message sent event
  ampli.messageSent({
    conversationId,
    messageId,
    messageLength: messageContent ? messageContent.length : 0,
    isMultiModel: models.length > 1 ? 'true' : 'false',
    // TS requires at least one string in the array as [string, ...string[]]
    modelIdList: models.length > 0 ? models as [string, ...string[]] : ['unknown'],
    primaryModelId: models.length > 0 ? models[0] : 'unknown'
  });
}

/**
 * Add any new analytics tracking methods below...
 */

<script lang="ts">
  import { onMount } from 'svelte';
  export let className = '';
  
  // Create an absolute URL using the current origin
  function createFullUrl(path: string): string {
    const origin = window.location.origin;
    return `${origin}${path}`;
  }
  
  function handleAuth0Login() {
    // Create the Auth0 login URL with the frontend origin and port explicitly encoded in the state
    const frontendOrigin = encodeURIComponent(window.location.origin);
    
    // Set the returnTo URL to the current origin + /auth to ensure we return to the frontend
    const returnToUrl = encodeURIComponent(`${window.location.origin}/auth`);
    
    // Redirect to the Auth0 login endpoint with the frontend origin
    window.location.href = `/api/v1/auths/oauth/auth0/login?frontendOrigin=${frontendOrigin}&returnTo=${returnToUrl}`;
  }
</script>

<button
  class={`flex items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 hover:text-blue-700 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700 dark:hover:text-white md:px-5 md:py-2.5 ${className}`}
  on:click={handleAuth0Login}
>
  <img
    src="https://cdn.auth0.com/styleguide/components/1.0.8/media/logos/img/badge.png"
    alt="Auth0"
    class="h-5 w-5"
  />
  <span>Continue with Auth0</span>
</button>

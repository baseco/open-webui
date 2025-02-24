<script lang="ts">
  export let className = '';
</script>

<button
  class={`flex items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 hover:text-blue-700 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700 dark:hover:text-white md:px-5 md:py-2.5 ${className}`}
  on:click={() => {
    window.location.href = '/api/v1/auths/oauth/auth0/login';
  }}
>
  <img
    src="https://cdn.auth0.com/styleguide/components/1.0.8/media/logos/img/badge.png"
    alt="Auth0"
    class="h-5 w-5"
  />
  <span>Continue with Auth0</span>
</button>

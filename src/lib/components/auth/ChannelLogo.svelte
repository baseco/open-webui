<script lang="ts">
  // Props for customization
  export let onClick: (() => void) | undefined = undefined;

  // Handle keyboard accessibility 
  function handleKeyDown(e: KeyboardEvent): void {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    }
  }
</script>

<!-- Use button instead of div for better accessibility when onClick is provided -->
{#if onClick}
  <button
    class="channel-logo-button z-20"
    on:click={onClick}
    on:keydown={handleKeyDown}
  >
    <img
      src="/auth/channel-logo.png"
      alt="Channel Logo"
      class="channel-logo-image"
    />

    <!-- Text fallback in case image doesn't load -->
    <div
      class="text-xl font-bold channel-logo-text-fallback"
    >
      Channel
    </div>
  </button>
{:else}
  <div
    class="channel-logo-container z-20"
  >
    <img
      src="/auth/channel-logo.png"
      alt="Channel Logo"
      class="channel-logo-image"
    />

    <!-- Text fallback in case image doesn't load -->
    <div
      class="text-xl font-bold channel-logo-text-fallback"
    >
      Channel
    </div>
  </div>
{/if}

<style>
  .channel-logo-button {
    position: relative;
    width: 180px;
    height: 40px;
    cursor: pointer;
    outline: none;
    background-color: transparent;
    border: none;
    padding: 0;
    margin: 0;
  }

  .channel-logo-container {
    position: relative;
    width: 180px;
    height: 40px;
  }

  .channel-logo-image {
    position: absolute;
    top: 0px;
    left: 0px;
    width: 70%;
    height: 70%;
    object-fit: contain;
  }

  .channel-logo-text-fallback {
    position: absolute;
    top: 10px;
    left: 20px;
    opacity: 0; /* Hidden by default, will show if image fails */
  }
</style>

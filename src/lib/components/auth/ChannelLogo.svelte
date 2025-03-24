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
    class="z-20 bg-transparent border-none p-0 m-0"
    on:click={onClick}
    on:keydown={handleKeyDown}
    style="
      position: relative;
      width: 180px;
      height: 40px;
      cursor: pointer;
      outline: none;
    "
  >
    <img
      src="/auth/channel-logo.png"
      alt="Channel Logo"
      style="
        position: absolute;
        top: 0px;
        left: 0px;
        width: 70%;
        height: 70%;
        object-fit: contain;
      "
    />

    <!-- Text fallback in case image doesn't load -->
    <div
      style="
        position: absolute;
        top: 10px;
        left: 20px;
        opacity: 0; /* Hidden by default, will show if image fails */
      "
      class="text-xl font-bold"
    >
      Channel
    </div>
  </button>
{:else}
  <div
    class="z-20"
    style="
      position: relative;
      width: 180px;
      height: 40px;
    "
  >
    <img
      src="/auth/channel-logo.png"
      alt="Channel Logo"
      style="
        position: absolute;
        top: 0px;
        left: 0px;
        width: 70%;
        height: 70%;
        object-fit: contain;
      "
    />

    <!-- Text fallback in case image doesn't load -->
    <div
      style="
        position: absolute;
        top: 10px;
        left: 20px;
        opacity: 0; /* Hidden by default, will show if image fails */
      "
      class="text-xl font-bold"
    >
      Channel
    </div>
  </div>
{/if}

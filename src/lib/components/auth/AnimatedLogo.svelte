<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import lottie from 'lottie-web';
  import { browser } from '$app/environment';

  // Props for customization
  export let onClick: (() => void) | undefined = undefined;
  export let isDarkMode: boolean = false;
  export let width: string = '180px';
  export let height: string = '40px';

  let animationContainer: HTMLElement;
  let animationInstance: any = null;
  let animationLoaded = false;

  // Handle keyboard accessibility 
  function handleKeyDown(e: KeyboardEvent): void {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    }
  }

  async function loadAnimation() {
    if (!browser || !animationContainer) return;
    
    if (animationInstance) {
      animationInstance.destroy();
      animationInstance = null;
    }

    try {
      // Choose the animation based on the theme
      const animationPath = isDarkMode 
        ? '/auth/animations/logo_mark-white.json' 
        : '/auth/animations/logo_mark-black.json';
      
      console.log(`Loading animation from ${animationPath}, isDarkMode: ${isDarkMode}`);
      
      // Create animation
      animationInstance = lottie.loadAnimation({
        container: animationContainer,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: animationPath
      });

      // Add event listeners
      animationInstance.addEventListener('DOMLoaded', () => {
        console.log('Animation DOM loaded');
        animationLoaded = true;
      });

      animationInstance.addEventListener('data_ready', () => {
        console.log('Animation data ready');
      });

      animationInstance.addEventListener('data_failed', (error: any) => {
        console.error('Animation data failed to load:', error);
      });

      animationInstance.addEventListener('error', (error: any) => {
        console.error('Animation error:', error);
      });
    } catch (error) {
      console.error('Error setting up animation:', error);
    }
  }

  // Watch for theme changes and reload animation
  $: if (browser && animationContainer && isDarkMode !== undefined) {
    console.log(`Theme changed to ${isDarkMode ? 'dark' : 'light'}`);
    loadAnimation();
  }

  onMount(() => {
    if (browser) {
      loadAnimation();
    }
  });

  onDestroy(() => {
    if (animationInstance) {
      animationInstance.destroy();
      animationInstance = null;
    }
  });
</script>

<!-- Use button for better accessibility when onClick is provided -->
{#if onClick}
  <button
    class="animated-logo-button"
    on:click={onClick}
    on:keydown={handleKeyDown}
    style="width: {width}; height: {height};"
  >
    <div 
      class="animation-container" 
      bind:this={animationContainer}
    ></div>
    
    <!-- Fallback text only shown if animation fails -->
    <div class="fallback-text" class:hidden={animationLoaded}>
      Channel
    </div>
  </button>
{:else}
  <div 
    class="animated-logo-container" 
    style="width: {width}; height: {height};"
  >
    <div 
      class="animation-container" 
      bind:this={animationContainer}
    ></div>
    
    <!-- Fallback text only shown if animation fails -->
    <div class="fallback-text" class:hidden={animationLoaded}>
      Channel
    </div>
  </div>
{/if}

<style>
  .animated-logo-button,
  .animated-logo-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .animated-logo-button {
    cursor: pointer;
    outline: none;
    background-color: transparent;
    border: none;
    padding: 0;
    margin: 0;
  }

  .animation-container {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .fallback-text {
    position: absolute;
    font-weight: bold;
    font-size: 1.25rem;
  }

  .hidden {
    display: none;
  }
</style>

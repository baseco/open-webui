<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';

  // Props for customization
  export let onClick: (() => void) | undefined = undefined;
  export let isDarkMode: boolean = false;
  export let width: string = '180px';
  export let height: string = '40px';

  let animationContainer: HTMLElement;
  let animationLoaded = false;

  // Handle keyboard accessibility 
  function handleKeyDown(e: KeyboardEvent): void {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    }
  }

  // Initialize or update the lottie-player element
  function setupLottiePlayer() {
    if (!browser || !animationContainer) return;
    
    try {
      // Choose the animation based on the theme
      const animationPath = isDarkMode 
        ? '/auth/animations/logo_mark-white.json' 
        : '/auth/animations/logo_mark-black.json';
      
      // Clear container first
      animationContainer.innerHTML = '';
      
      // Create lottie-player element
      const player = document.createElement('lottie-player');
      player.setAttribute('src', animationPath);
      player.setAttribute('background', 'transparent');
      player.setAttribute('speed', '1');
      player.setAttribute('loop', '');
      player.setAttribute('autoplay', '');
      player.style.width = '100%';
      player.style.height = '100%';
      
      // Add error handler
      player.addEventListener('error', (e) => {
        console.error('Lottie player error:', e);
        animationLoaded = false;
      });
      
      // Add load handler
      player.addEventListener('load', () => {
        animationLoaded = true;
      });
      
      // Add to DOM
      animationContainer.appendChild(player);
      
    } catch (error) {
      console.error('Error setting up animation:', error);
      animationLoaded = false;
    }
  }

  // Watch for theme changes and reload animation
  $: if (browser && animationContainer && isDarkMode !== undefined) {
    setupLottiePlayer();
  }

  onMount(() => {
    if (browser) {
      setupLottiePlayer();
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

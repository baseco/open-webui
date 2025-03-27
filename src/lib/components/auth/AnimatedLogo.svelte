<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';

  // Props for customization
  export let onClick: (() => void) | undefined = undefined;
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
    
    // Clear container first
    animationContainer.innerHTML = '';
    
    // Detect theme
    const isDark = document.documentElement.classList.contains('dark');
    const animationPath = isDark 
      ? '/auth/animations/logo_mark-white.json' 
      : '/auth/animations/logo_mark-black.json';
    
    // Create and configure lottie-player element
    const player = document.createElement('lottie-player');
    Object.assign(player, {
      src: animationPath,
      background: 'transparent',
      speed: 1,
      loop: true,
      autoplay: true
    });
    player.style.cssText = 'width: 100%; height: 100%;';
    
    // Set up event listeners
    player.addEventListener('error', () => {
      animationLoaded = false;
    });
    
    player.addEventListener('load', () => {
      animationLoaded = true;
    });
    
    // Add to DOM
    animationContainer.appendChild(player);
  }

  onMount(() => {
    if (browser) {
      // Initial setup
      setupLottiePlayer();
      
      // Watch for theme changes
      const observer = new MutationObserver(() => {
        setupLottiePlayer();
      });
      
      observer.observe(document.documentElement, { 
        attributes: true,
        attributeFilter: ['class'] 
      });
      
      return () => observer.disconnect();
    }
  });
</script>

<!-- Common template structure for both button and div variants -->
{#if onClick}
  <button
    class="animated-logo-container"
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
  .animated-logo-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* Additional styles for button variant */
  button.animated-logo-container {
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

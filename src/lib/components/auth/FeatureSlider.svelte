<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { tweened } from 'svelte/motion';
  import { fade } from 'svelte/transition';
  import { cubicInOut } from 'svelte/easing';

  // Define types in a more Svelte-friendly way
  type FeatureSlide = {
    title?: string;
    description?: string;
    image: string;
  };

  export let slides: FeatureSlide[] = [];
  export let autoPlayInterval: number = 8000;

  let currentSlide = 0;
  let interval: ReturnType<typeof setInterval>;
  let kenBurnsInterval: ReturnType<typeof setInterval>;
  let transitioning = false;
  
  // Ken Burns effect parameters
  const kenBurnsDuration = autoPlayInterval - 1000; // Slightly shorter than slide duration
  let zoomLevel = tweened(1, {
    duration: kenBurnsDuration,
    easing: cubicInOut
  });
  
  let panX = tweened(0, {
    duration: kenBurnsDuration,
    easing: cubicInOut
  });
  
  let panY = tweened(0, {
    duration: kenBurnsDuration,
    easing: cubicInOut
  });

  // Start Ken Burns effect for current slide
  function startKenBurnsEffect() {
    // Clear any existing animation
    if (kenBurnsInterval) clearInterval(kenBurnsInterval);
    
    // Randomize the effect for each slide
    const startZoom = 1;
    const endZoom = 1 + (Math.random() * 0.15); // Zoom between 1x and 1.15x
    
    // Random pan within reasonable bounds
    const startPanX = 0;
    const startPanY = 0;
    const endPanX = (Math.random() - 0.5) * 5; // -2.5% to 2.5% pan
    const endPanY = (Math.random() - 0.5) * 5; // -2.5% to 2.5% pan
    
    // Reset values
    zoomLevel.set(startZoom, { duration: 0 });
    panX.set(startPanX, { duration: 0 });
    panY.set(startPanY, { duration: 0 });
    
    // Start animation immediately
    zoomLevel.set(endZoom);
    panX.set(endPanX);
    panY.set(endPanY);
  }

  async function goToSlide(index: number) {
    if (transitioning || index === currentSlide) return;
    
    transitioning = true;
    
    // Stop current Ken Burns effect
    if (kenBurnsInterval) clearInterval(kenBurnsInterval);
    
    // Update slide index
    currentSlide = index;
    
    // Wait a brief moment for the fade transition to complete
    setTimeout(() => {
      // Start Ken Burns effect for new slide
      startKenBurnsEffect();
      transitioning = false;
    }, 600);
  }

  function nextSlide(): void {
    const nextIndex = (currentSlide === slides.length - 1) ? 0 : currentSlide + 1;
    goToSlide(nextIndex);
  }

  function prevSlide(): void {
    const prevIndex = (currentSlide === 0) ? slides.length - 1 : currentSlide - 1;
    goToSlide(prevIndex);
  }

  onMount(() => {
    // Start Ken Burns effect for first slide
    startKenBurnsEffect();
    
    // Auto-advance slides
    interval = setInterval(() => {
      nextSlide();
    }, autoPlayInterval);
  });

  onDestroy(() => {
    if (interval) clearInterval(interval);
    if (kenBurnsInterval) clearInterval(kenBurnsInterval);
  });
</script>

<div class="w-full h-full flex flex-col items-center justify-between">
  <!-- Ken Burns Slide Container -->
  <div class="flex-grow w-full relative overflow-hidden" style="min-height: 400px;">
    {#key currentSlide}
      <div 
        class="w-full h-full absolute inset-0 flex flex-col items-center justify-center p-6"
        transition:fade={{ duration: 600 }}
      >
        <!-- Content wrapper with Ken Burns effect -->
        <div class="w-full max-w-lg flex flex-col items-center justify-center">
          {#if slides[currentSlide]?.title || slides[currentSlide]?.description}
            <div class="text-center mb-8">
              {#if slides[currentSlide]?.title}
                <h2 class="text-2xl font-bold mb-4">{slides[currentSlide].title}</h2>
              {/if}
              {#if slides[currentSlide]?.description}
                <p class="text-gray-600">{slides[currentSlide].description}</p>
              {/if}
            </div>
          {/if}
          
          <!-- Image with Ken Burns effect -->
          <div 
            class="rounded-lg overflow-hidden shadow-lg" 
            style="max-width: 100%;"
          >
            <div class="overflow-hidden rounded-lg">
              <img
                src={slides[currentSlide]?.image || "/placeholder.svg"}
                alt={slides[currentSlide]?.title || "Feature image"}
                class="w-full h-auto object-cover transform origin-center transition-all duration-100 ease-linear"
                style="
                  transform: scale({$zoomLevel}) translate({$panX}%, {$panY}%);
                  max-height: 300px;
                "
              />
            </div>
          </div>
        </div>
      </div>
    {/key}
  </div>

  <!-- Navigation dots -->
  <div class="mt-6 flex items-center justify-center space-x-8">
    <button 
      class="rounded-full bg-white/80 hover:bg-white p-2 transition-colors"
      on:click={prevSlide}
      disabled={transitioning}
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m15 18-6-6 6-6"/>
      </svg>
    </button>

    <div class="flex space-x-2">
      {#each slides as _, index}
        <button
          class={`w-2 h-2 rounded-full transition-all duration-300 ${currentSlide === index ? "bg-primary w-4" : "bg-gray-300"}`}
          on:click={() => goToSlide(index)}
          disabled={transitioning}
        />
      {/each}
    </div>

    <button 
      class="rounded-full bg-white/80 hover:bg-white p-2 transition-colors"
      on:click={nextSlide}
      disabled={transitioning}
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m9 18 6-6-6-6"/>
      </svg>
    </button>
  </div>
</div>

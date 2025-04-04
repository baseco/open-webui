<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { fade } from 'svelte/transition';

  // Define types in a more Svelte-friendly way
  type FeatureSlide = {
    title?: string;
    description?: string;
    image: string;
  };

  export let slides: FeatureSlide[] = [];
  export let autoPlayInterval: number = 8000;
  // Add ability to externally control current slide
  export let currentSlide = 0;

  const dispatch = createEventDispatcher();
  let interval: ReturnType<typeof setInterval>;
  let transitioning = false;

  async function goToSlide(index: number) {
    if (transitioning || index === currentSlide) return;
    
    transitioning = true;
    
    // Update slide index
    currentSlide = index;
    
    // Notify parent of slide change
    dispatch('slideChange', { currentSlide });

    // Wait a brief moment for the fade transition to complete
    setTimeout(() => {
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
    // Auto-advance slides
    interval = setInterval(() => {
      nextSlide();
    }, autoPlayInterval);
  });

  onDestroy(() => {
    if (interval) clearInterval(interval);
  });
</script>

<div class="w-full h-full flex flex-col items-center justify-between">
  <!-- Slide Container -->
  <div class="flex-grow w-full relative overflow-hidden" style="min-height: 400px;">
    {#key currentSlide}
      <div 
        class="w-full h-full absolute inset-0 flex flex-col items-center justify-center p-6"
        transition:fade={{ duration: 600 }}
      >
        <div class="w-full max-w-full flex flex-col items-center justify-center">
          {#if slides[currentSlide]?.title || slides[currentSlide]?.description}
            <div class="mb-8 w-full">
              {#if slides[currentSlide]?.title}
                <h2 class="text-[20px] font-[300] text-[#4E4E4E] mb-6 self-start px-[5%]" style="font-family: Inter; font-weight: 300;">{slides[currentSlide].title}</h2>
              {/if}
              {#if slides[currentSlide]?.description}
                <p class="text-gray-600">{slides[currentSlide].description}</p>
              {/if}
            </div>
          {/if}
          
          <!-- Image container -->
          <div class="rounded-lg overflow-hidden w-full">
            <img
              src={slides[currentSlide]?.image || "/placeholder.svg"}
              alt={slides[currentSlide]?.title || "Feature image"}
              class="w-full h-auto object-contain"
              style="max-height: 70vh;"
            />
          </div>
        </div>
      </div>
    {/key}
  </div>

  <!-- Navigation dots -->
  <div class="mt-4 md:mt-6 flex items-center justify-center space-x-6 md:space-x-8">
    <button 
      class="rounded-full bg-black/60 text-white hover:bg-black/80 p-2 md:p-3 transition-colors shadow-md"
      on:click={prevSlide}
      disabled={transitioning}
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="md:w-5 md:h-5">
        <path d="m15 18-6-6 6-6"/>
      </svg>
    </button>

    <div class="flex space-x-2 md:space-x-3">
      {#each slides as _, index}
        <button
          class={`h-2 md:h-3 rounded-full transition-all duration-300 ${currentSlide === index ? "bg-white w-6 md:w-8" : "bg-gray-300 w-2 md:w-3"}`}
          on:click={() => goToSlide(index)}
          disabled={transitioning}
        />
      {/each}
    </div>

    <button 
      class="rounded-full bg-black/60 text-white hover:bg-black/80 p-2 md:p-3 transition-colors shadow-md"
      on:click={nextSlide}
      disabled={transitioning}
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="md:w-5 md:h-5">
        <path d="m9 18 6-6-6-6"/>
      </svg>
    </button>
  </div>
</div>

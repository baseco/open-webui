<script lang="ts">
  // Optional props for customization
  export let opacity: number = 0.5;
  export let videoSrc: string = "/auth/background-video.mp4";
  
  // Handle video loading error
  function handleVideoError(e: Event): void {
    console.error('Video failed to load:', e);
    // Show the fallback background
    const fallbackEl = document.querySelector('.fallback-bg') as HTMLDivElement;
    if (fallbackEl) fallbackEl.style.display = 'block';
  }
  
  function handleVideoLoaded(): void {
    console.log('Video loaded successfully');
  }
</script>

<div class="absolute inset-0 z-0 overflow-hidden">
  <video
    autoplay
    loop
    muted
    playsinline
    on:loadeddata={handleVideoLoaded}
    on:error={handleVideoError}
    class="absolute min-h-[120%] min-w-[120%] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 object-cover"
    style="opacity: {opacity};"
  >
    <source src={videoSrc} type="video/mp4" />
  </video>
  
  <!-- Fallback static background that shows only if video fails -->
  <div class="fallback-bg absolute inset-0 bg-gradient-to-br from-blue-900 to-purple-900" style="display: none;"></div>
</div>

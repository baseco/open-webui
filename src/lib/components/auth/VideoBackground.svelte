<script lang="ts">
  // Optional props for customization
  export let opacity: number = 0.5;
  export let videoSrc: string = "/auth/background-video.mp4";
</script>

<div class="absolute inset-0 z-0 overflow-hidden">
  <video
    autoplay
    loop
    muted
    playsinline
    class="absolute min-h-[120%] min-w-[120%] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 object-cover"
    style="opacity: {opacity};"
  >
    <source src={videoSrc} type="video/mp4" />
  </video>
</div>

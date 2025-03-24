<script lang="ts">
  // Props for customization
  export let className: string = "";
  
  // Function to handle mouse down event, if needed
  export let onMouseDown: ((e: MouseEvent) => void) | undefined = undefined;
</script>

<div 
  class="mx-auto w-full max-w-md overflow-hidden rounded-lg bg-white/30 backdrop-blur-xl backdrop-filter shadow-lg border border-white/20 {className}"
  on:mousedown={onMouseDown}
>
  <slot></slot>
</div>

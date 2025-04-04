<script lang="ts">
    import { getContext } from 'svelte';
    import Modal from "$lib/components/common/Modal.svelte";
    
    const i18n = getContext('i18n');
    export let show = false;
</script>

<Modal bind:show size="sm">
    <div class="flex flex-col p-5 gap-4">
        <div class="flex flex-col items-center justify-center">
            <h2 class="text-xl font-semibold text-center">Enough is enough</h2>
            <p class="mt-2 text-sm text-center">
                You have reached your message limit. Please contact the administrator for more information.
            </p>
        </div>
        <div class="flex justify-center">
            <button
                class="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg transition-colors"
                on:click={() => {
                    show = false;
                }}
            >
                {$i18n.t('Close')}
            </button>
        </div>
    </div>
</Modal>
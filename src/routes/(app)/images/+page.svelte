<script lang="ts">
    import { getContext } from 'svelte';
    import { onMount } from 'svelte';
    import { user } from '$lib/stores';
    import { goto } from '$app/navigation';

    const i18n = getContext('i18n');

    onMount(() => {
        // Ensure user has access
        if (!$user || !['user', 'admin'].includes($user.role)) {
            goto('/');
        }
    });
</script>

<div class="h-full w-full bg-white dark:bg-gray-900">
    <iframe
        src="https://channel.bot"
        title={$i18n.t('Channel Bot Images')}
        class="w-full h-full border-0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
    />
</div>

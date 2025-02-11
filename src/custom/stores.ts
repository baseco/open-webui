import { writable } from 'svelte/store';

// Store to control visibility of UI elements
export const customUIControls = writable({
    showControlsButton: false,
    showChangelog: false,
    showUpdateNotifications: false
});

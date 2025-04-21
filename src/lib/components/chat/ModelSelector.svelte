<script lang="ts">
	import { models, showSettings, settings, user, mobile, config } from '$lib/stores';
	import { onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Selector from './ModelSelector/Selector.svelte';
	import Tooltip from '../common/Tooltip.svelte';

	import { updateUserSettings } from '$lib/apis/users';
	const i18n = getContext('i18n');

	export let selectedModels = [''];
	export let disabled = false;

	export let showSetDefault = true;

	// Define availableModels first
	let availableModels = [];

	// Filter to exclude arena models and respect active status
	$: {
		// Use more flexible truthy checking for is_active
		availableModels = $models.filter(m => 
			// Exclude arena models
			m?.owned_by !== 'arena' && 
			// Include models with truthy is_active (1, true, etc)
			!!m.is_active
		);
	}

	const saveDefaultModel = async () => {
		const hasEmptyModel = selectedModels.filter((it) => it === '');
		if (hasEmptyModel.length) {
			toast.error($i18n.t('Choose a model before saving...'));
			return;
		}
		settings.set({ ...$settings, models: selectedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });

		toast.success($i18n.t('Default model updated'));
	};

	$: if (selectedModels.length > 0 && availableModels.length > 0) {
		selectedModels = selectedModels.map((model) =>
			availableModels.map((m) => m.id).includes(model) ? model : ''
		);
	}
</script>

<div class="flex flex-col w-full items-start">
	{#each selectedModels as selectedModel, selectedModelIdx}
		<div class="flex w-full max-w-fit">
			<div class="overflow-hidden w-full">
				<div class="mr-1 max-w-full">
					<Selector
						id={`${selectedModelIdx}`}
						placeholder={$i18n.t('Select a model')}
						items={availableModels.map((model) => {
							return {
								value: model.id,
								label: model.name,
								model: model
							};
						})}
						showTemporaryChatControl={$user.role === 'user'
							? ($user?.permissions?.chat?.temporary ?? true)
							: true}
						bind:value={selectedModel}
					/>
				</div>
			</div>

			{#if selectedModelIdx === 0}
				<div
					class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
				>
					<Tooltip content={$i18n.t('Add Model')}>
						<button
							class=" "
							{disabled}
							on:click={() => {
								if (selectedModels.length < 3) {
									selectedModels = [...selectedModels, ''];
								} else {
									toast.error($i18n.t('Maximum of 3 models allowed for multimodel chat'));
								}
							}}
							aria-label="Add Model"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="size-3.5"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{:else}
				<div
					class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
				>
					<Tooltip content={$i18n.t('Remove Model')}>
						<button
							{disabled}
							on:click={() => {
								selectedModels.splice(selectedModelIdx, 1);
								selectedModels = selectedModels;
							}}
							aria-label="Remove Model"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="size-3"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{/if}
		</div>
	{/each}
</div>

{#if showSetDefault}
	<div class=" absolute text-left mt-[1px] ml-1 text-[0.7rem] text-gray-500 font-primary">
		<button on:click={saveDefaultModel}> {$i18n.t('Set as default')}</button>
	</div>
{/if}

<script lang="ts">
	import { marked } from 'marked';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { onMount, getContext, tick } from 'svelte';
	const i18n = getContext('i18n');

	import { WEBUI_NAME, config, mobile, models as _models, settings, user } from '$lib/stores';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import {
		createNewModel,
		getBaseModels,
		toggleModelById,
		updateModelById,
		getModelById
	} from '$lib/apis/models';

	import { getModels } from '$lib/apis';
	import Search from '$lib/components/icons/Search.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';
	import { toast } from 'svelte-sonner';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ConfigureModelsModal from './Models/ConfigureModelsModal.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import ManageModelsModal from './Models/ManageModelsModal.svelte';

	let importFiles;
	let modelsImportInputElement: HTMLInputElement;

	let models = null;

	let workspaceModels = null;
	let baseModels = null;

	let filteredModels = [];
	let selectedModelId = null;

	let showConfigModal = false;
	let showManageModal = false;
	let showDisableAllConfirm = false;
	let disablingInProgress = false;
	let disabledCount = 0;
	let totalModelsToDisable = 0;
	let disablingProgress = 0;

	$: if (models) {
		filteredModels = models
			.filter((m) => searchValue === '' || m.name.toLowerCase().includes(searchValue.toLowerCase()))
			.sort((a, b) => {
				// First sort by active status (active models first)
				if ((a.is_active ?? true) !== (b.is_active ?? true)) {
					return (b.is_active ?? true) - (a.is_active ?? true);
				}
				// Then sort alphabetically within each group
				return a.name.localeCompare(b.name);
			});
		
		// Log model counts and status in admin panel
		console.log('[AdminModels] Total models count:', models.length);
		console.log('[AdminModels] Active models count:', models.filter(m => m.is_active !== false).length);
		console.log('[AdminModels] Inactive models count:', models.filter(m => m.is_active === false).length);
		
		// Log complete model data for better debugging
		console.log('[AdminModels] Full model data by source:', models.reduce((acc, m) => {
			const source = m.owned_by || 'unknown';
			if (!acc[source]) acc[source] = [];
			acc[source].push({
				id: m.id,
				name: m.name,
				owned_by: m.owned_by,
				is_active: m.is_active,
				direct: m.direct,
				base_model_id: m.base_model_id
			});
			return acc;
		}, {}));
		
		console.log('[AdminModels] Active model names by source:', 
			models.filter(m => m.is_active !== false).reduce((acc, m) => {
				const source = m.owned_by || 'unknown';
				if (!acc[source]) acc[source] = [];
				acc[source].push(m.name);
				return acc;
			}, {})
		);
	}

	let searchValue = '';

	const downloadModels = async (models) => {
		let blob = new Blob([JSON.stringify(models)], {
			type: 'application/json'
		});
		saveAs(blob, `models-export-${Date.now()}.json`);
	};

	const init = async () => {
		console.log('[AdminModels] Initializing models data...');
		workspaceModels = await getBaseModels(localStorage.token);
		baseModels = await getModels(localStorage.token, null, true);

		console.log('[AdminModels] Workspace models from getBaseModels:', workspaceModels);
		console.log('[AdminModels] Base models from getModels:', baseModels);

		models = baseModels.map((m) => {
			const workspaceModel = workspaceModels.find((wm) => wm.id === m.id);

			if (workspaceModel) {
				return {
					...m,
					...workspaceModel
				};
			} else {
				return {
					...m,
					id: m.id,
					name: m.name,

					is_active: true
				};
			}
		});

		console.log('[AdminModels] Merged models data:', models.map(m => ({
			id: m.id,
			name: m.name,
			is_active: m.is_active,
			source: workspaceModels.find(wm => wm.id === m.id) ? 'workspace' : 'default'
		})));
	};

	const upsertModelHandler = async (model) => {
		model.base_model_id = null;

		if (workspaceModels.find((m) => m.id === model.id)) {
			const res = await updateModelById(localStorage.token, model.id, model).catch((error) => {
				return null;
			});

			if (res) {
				toast.success($i18n.t('Model updated successfully'));
			}
		} else {
			const res = await createNewModel(localStorage.token, model).catch((error) => {
				return null;
			});

			if (res) {
				toast.success($i18n.t('Model updated successfully'));
			}
		}

		_models.set(
			await getModels(
				localStorage.token,
				$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null)
			)
		);
		await init();
	};

	const toggleModelHandler = async (model) => {
		console.log('[AdminModels] Toggling model:', model.id, model.name, 'Current is_active:', model.is_active);
		
		if (!Object.keys(model).includes('base_model_id')) {
			console.log('[AdminModels] Creating new model entry for:', model.id);
			await createNewModel(localStorage.token, {
				id: model.id,
				name: model.name,
				base_model_id: null,
				meta: {},
				params: {},
				access_control: {},
				is_active: model.is_active
			}).catch((error) => {
				console.error('[AdminModels] Error creating model:', error);
				return null;
			});
		} else {
			console.log('[AdminModels] Toggling existing model:', model.id);
			await toggleModelById(localStorage.token, model.id);
		}

		// await init();
		const updatedModels = await getModels(
			localStorage.token,
			$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null)
		);
		console.log('[AdminModels] Updated models after toggle:', updatedModels);
		_models.set(updatedModels);
	};

	const disableAllModels = async () => {
		try {
			console.log("[AdminModels] disableAllModels called - showing confirmation dialog");
			// Show confirmation dialog
			showDisableAllConfirm = true;
		} catch (error) {
			console.error('Error disabling models:', error);
			toast.error($i18n.t('Error disabling models'));
		}
	};

	const confirmDisableAllModels = async () => {
		try {
			console.log("[AdminModels] confirmDisableAllModels called - starting process");
			// Start with a loading toast
			const toastId = toast.loading($i18n.t('Disabling all models...'));
			
			// Set in progress flag and reset counters
			disablingInProgress = true;
			disabledCount = 0;
			
			// First, refresh the model data to ensure we have the latest state
			console.log("[AdminModels] Refreshing model data before disabling");
			workspaceModels = await getBaseModels(localStorage.token);
			baseModels = await getModels(localStorage.token, null, true);
			
			// Log details about our workspace models
			console.log("[AdminModels] Workspace models:", workspaceModels);
			
			// Reinitialize models with fresh data
			models = baseModels.map((m) => {
				const workspaceModel = workspaceModels.find((wm) => wm.id === m.id);

				if (workspaceModel) {
					return {
						...m,
						...workspaceModel
					};
				} else {
					return {
						...m,
						id: m.id,
						name: m.name,
						is_active: true
					};
				}
			});
			
			console.log("[AdminModels] Fresh models data loaded:", models.length, "models");
			console.log("[AdminModels] Detailed model state:", models.map(m => ({ id: m.id, name: m.name, is_active: m.is_active })));
			
			// Get only active models (these are the ones we need to disable)
			const activeModels = models.filter(model => model.is_active !== false);
			totalModelsToDisable = activeModels.length;
			
			console.log("[AdminModels] Active models to disable:", totalModelsToDisable);
			console.log("[AdminModels] Active model details:", activeModels.map(m => ({ id: m.id, name: m.name })));
			
			if (totalModelsToDisable === 0) {
				console.log("[AdminModels] No active models found to disable");
				toast.success($i18n.t('All models are already disabled'), { id: toastId });
				disablingInProgress = false;
				showDisableAllConfirm = false;
				return;
			}
			
			// Process each active model in sequence with careful error handling
			for (let i = 0; i < activeModels.length; i++) {
				const model = activeModels[i];
				disablingProgress = Math.round((i / totalModelsToDisable) * 100);
				
				// Update the toast message with progress
				toast.loading(`${$i18n.t('Disabling models')}: ${i}/${totalModelsToDisable} (${disablingProgress}%)`, { id: toastId });
				
				try {
					console.log(`[AdminModels] [${i+1}/${activeModels.length}] Processing model: ${model.id} (${model.name})`);
					
					// Log current model state
					console.log(`[AdminModels] Current state for ${model.id}: is_active=${model.is_active}`);
					
					// Get the complete model data first to make sure we have all required fields
					console.log(`[AdminModels] Fetching complete model data for ${model.id}...`);
					const completeModelData = await getModelById(localStorage.token, model.id);
					console.log(`[AdminModels] Complete model data for ${model.id}:`, completeModelData);
					
					if (!completeModelData) {
						console.error(`[AdminModels] Failed to fetch complete data for model ${model.id}`);
						continue;
					}
					
					// Force a specific update using updateModelById to explicitly set is_active to false
					// Include ALL required fields from the original model
					console.log(`[AdminModels] Explicitly setting model ${model.id} to inactive...`);
					
					// Create update payload with all required fields
					const updatePayload = {
						...completeModelData,
						is_active: false
					};
					console.log(`[AdminModels] Update payload for ${model.id}:`, updatePayload);
					
					// We'll use direct API call with detailed response logging
					const updateResponse = await fetch(`${WEBUI_API_BASE_URL}/models/model/update?id=${encodeURIComponent(model.id)}`, {
						method: 'POST',
						headers: {
							Accept: 'application/json',
							'Content-Type': 'application/json',
							authorization: `Bearer ${localStorage.token}`
						},
						body: JSON.stringify(updatePayload)
					});
					
					// Log the complete response
					const responseText = await updateResponse.text();
					console.log(`[AdminModels] Update API response for ${model.id}:`, updateResponse.status, responseText);
					
					if (updateResponse.ok) {
						console.log(`[AdminModels] Successfully updated model ${model.id} to inactive`);
						disabledCount++;
						
						// Verify the model was actually updated by fetching it again
						console.log(`[AdminModels] Verifying model ${model.id} state...`);
						const verifyResponse = await getModelById(localStorage.token, model.id);
						console.log(`[AdminModels] Verification response for ${model.id}:`, verifyResponse);
						
						if (verifyResponse && verifyResponse.is_active === false) {
							console.log(`[AdminModels] Verified: model ${model.id} is now inactive`);
						} else {
							console.log(`[AdminModels] WARNING: model ${model.id} state verification failed!`);
						}
					} else {
						console.error(`[AdminModels] Failed to update model ${model.id}: Status ${updateResponse.status}`);
					}
					
					// Wait between operations - give the server more time
					console.log(`[AdminModels] Waiting before processing next model...`);
					await new Promise(resolve => setTimeout(resolve, 1000));
				} catch (err) {
					console.error(`[AdminModels] Error processing model ${model.id}:`, err);
				}
			}
			
			// Final success toast
			if (disabledCount === totalModelsToDisable) {
				toast.success($i18n.t('All models disabled successfully'), { id: toastId });
			} else {
				toast.success(`${$i18n.t('Models disabled')}: ${disabledCount}/${totalModelsToDisable}`, { id: toastId });
			}
			
			console.log(`[AdminModels] Disabled ${disabledCount} out of ${totalModelsToDisable} models`);
			
			// Wait a longer time before refreshing - critical for backend to process everything
			console.log("[AdminModels] Waiting 5 seconds before refreshing data...");
			await new Promise(resolve => setTimeout(resolve, 5000));
			
			// Force a complete refresh of the global models store first
			console.log("[AdminModels] Refreshing global models store");
			const refreshedModels = await getModels(localStorage.token);
			console.log("[AdminModels] Refreshed models state:", refreshedModels);
			
			// Debug: Check if any models are still showing as active
			console.log("[AdminModels] Models still active in refreshed data:", 
				refreshedModels.filter(m => m.is_active !== false).map(m => m.name));
			
			await _models.set(refreshedModels);
			
			// Force complete refresh of all model data
			console.log("[AdminModels] Force reloading all model data");
			workspaceModels = await getBaseModels(localStorage.token);
			baseModels = await getModels(localStorage.token, null, true);
			console.log("[AdminModels] Refreshed workspace models:", workspaceModels);
			
			// Run the initialization function again
			console.log("[AdminModels] Reinitializing admin panel");
			await init();
			
			// Close the confirmation dialog and reset flags
			disablingInProgress = false;
			showDisableAllConfirm = false;
		} catch (error) {
			console.error('[AdminModels] Error disabling models:', error);
			toast.error($i18n.t('Error disabling models'));
			disablingInProgress = false;
			showDisableAllConfirm = false;
		}
	};

	onMount(async () => {
		init();
	});
</script>

<ConfigureModelsModal bind:show={showConfigModal} initHandler={init} />
<ManageModelsModal bind:show={showManageModal} />

<ConfirmDialog
	title={$i18n.t('Disable All Models')}
	body={disablingInProgress ? 
		`${$i18n.t('Disabling models')}: ${disabledCount}/${totalModelsToDisable} (${disablingProgress}%)`
		: $i18n.t('Are you sure you want to disable all models? This will affect all models in the system.')}
	confirmText={disablingInProgress ? $i18n.t('Please wait...') : $i18n.t('Disable All')}
	bind:show={showDisableAllConfirm}
	on:confirm={confirmDisableAllModels}
	disableConfirm={disablingInProgress}
/>

{#if models !== null}
	{#if selectedModelId === null}
		<div class="flex flex-col gap-1 mt-1.5 mb-2">
			<div class="flex justify-between items-center">
				<div class="flex items-center md:self-center text-xl font-medium px-0.5">
					{$i18n.t('Models')}
					<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-50 dark:bg-gray-850" />
					<span class="text-lg font-medium text-gray-500 dark:text-gray-300"
						>{filteredModels.length}</span
					>
				</div>

				<div class="flex items-center gap-1.5">
					<Tooltip content={$i18n.t('Disable All Models')}>
						<button
							class="p-1 rounded-full flex gap-1 items-center text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
							type="button"
							on:click={disableAllModels}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="w-4 h-4"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636" />
							</svg>
						</button>
					</Tooltip>
					
					<Tooltip content={$i18n.t('Manage Models')}>
						<button
							class=" p-1 rounded-full flex gap-1 items-center"
							type="button"
							on:click={() => {
								showManageModal = true;
							}}
						>
							<ArrowDownTray />
						</button>
					</Tooltip>

					<Tooltip content={$i18n.t('Settings')}>
						<button
							class=" p-1 rounded-full flex gap-1 items-center"
							type="button"
							on:click={() => {
								showConfigModal = true;
							}}
						>
							<Cog6 />
						</button>
					</Tooltip>
				</div>
			</div>

			<div class=" flex flex-1 items-center w-full space-x-2">
				<div class="flex flex-1 items-center">
					<div class=" self-center ml-1 mr-3">
						<Search className="size-3.5" />
					</div>
					<input
						class=" w-full text-sm py-1 rounded-r-xl outline-hidden bg-transparent"
						bind:value={searchValue}
						placeholder={$i18n.t('Search Models')}
					/>
				</div>
			</div>
		</div>

		<div class=" my-2 mb-5" id="model-list">
			{#if models.length > 0}
				{#each filteredModels as model, modelIdx (model.id)}
					<div
						class=" flex space-x-4 cursor-pointer w-full px-3 py-2 dark:hover:bg-white/5 hover:bg-black/5 rounded-lg transition"
						id="model-item-{model.id}"
					>
						<button
							class=" flex flex-1 text-left space-x-3.5 cursor-pointer w-full"
							type="button"
							on:click={() => {
								selectedModelId = model.id;
							}}
						>
							<div class=" self-center w-8">
								<div
									class=" rounded-full object-cover {(model?.is_active ?? true)
										? ''
										: 'opacity-50 dark:opacity-50'} "
								>
									<img
										src={model?.meta?.profile_image_url ?? '/static/favicon.png'}
										alt="modelfile profile"
										class=" rounded-full w-full h-auto object-cover"
									/>
								</div>
							</div>

							<div class=" flex-1 self-center {(model?.is_active ?? true) ? '' : 'text-gray-500'}">
								<Tooltip
									content={marked.parse(
										!!model?.meta?.description
											? model?.meta?.description
											: model?.ollama?.digest
												? `${model?.ollama?.digest} **(${model?.ollama?.modified_at})**`
												: model.id
									)}
									className=" w-fit"
									placement="top-start"
								>
									<div class="  font-semibold line-clamp-1">{model.name}</div>
								</Tooltip>
								<div class=" text-xs overflow-hidden text-ellipsis line-clamp-1 text-gray-500">
									<span class=" line-clamp-1">
										{!!model?.meta?.description
											? model?.meta?.description
											: model?.ollama?.digest
												? `${model.id} (${model?.ollama?.digest})`
												: model.id}
									</span>
								</div>
							</div>
						</button>
						<div class="flex flex-row gap-0.5 items-center self-center">
							<button
								class="self-center w-fit text-sm px-2 py-2 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
								type="button"
								on:click={() => {
									selectedModelId = model.id;
								}}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="1.5"
									stroke="currentColor"
									class="w-4 h-4"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
									/>
								</svg>
							</button>

							<div class="ml-1">
								<Tooltip
									content={(model?.is_active ?? true) ? $i18n.t('Enabled') : $i18n.t('Disabled')}
								>
									<Switch
										bind:state={model.is_active}
										on:change={async () => {
											toggleModelHandler(model);
										}}
									/>
								</Tooltip>
							</div>
						</div>
					</div>
				{/each}
			{:else}
				<div class="flex flex-col items-center justify-center w-full h-20">
					<div class="text-gray-500 dark:text-gray-400 text-xs">
						{$i18n.t('No models found')}
					</div>
				</div>
			{/if}
		</div>

		{#if $user?.role === 'admin'}
			<div class=" flex justify-end w-full mb-3">
				<div class="flex space-x-1">
					<input
						id="models-import-input"
						bind:this={modelsImportInputElement}
						bind:files={importFiles}
						type="file"
						accept=".json"
						hidden
						on:change={() => {
							console.log(importFiles);

							let reader = new FileReader();
							reader.onload = async (event) => {
								let savedModels = JSON.parse(event.target.result);
								console.log(savedModels);

								for (const model of savedModels) {
									if (Object.keys(model).includes('base_model_id')) {
										if (model.base_model_id === null) {
											upsertModelHandler(model);
										}
									} else {
										if (model?.info ?? false) {
											if (model.info.base_model_id === null) {
												upsertModelHandler(model.info);
											}
										}
									}
								}

								await _models.set(
									await getModels(
										localStorage.token,
										$config?.features?.enable_direct_connections &&
											($settings?.directConnections ?? null)
									)
								);
								init();
							};

							reader.readAsText(importFiles[0]);
						}}
					/>

					<button
						class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
						on:click={() => {
							modelsImportInputElement.click();
						}}
					>
						<div class=" self-center mr-2 font-medium line-clamp-1">
							{$i18n.t('Import Presets')}
						</div>

						<div class=" self-center">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="w-3.5 h-3.5"
							>
								<path
									fill-rule="evenodd"
									d="M4 2a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5V6.621a1.5 1.5 0 0 0-.44-1.06L9.94 2.439A1.5 1.5 0 0 0 8.878 2H4Zm4 9.5a.75.75 0 0 1-.75-.75V8.06l-.72.72a.75.75 0 0 1-1.06-1.06l2-2a.75.75 0 0 1 1.06 0l2 2a.75.75 0 1 1-1.06 1.06l-.72-.72v2.69a.75.75 0 0 1-.75.75Z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					</button>

					<button
						class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
						on:click={async () => {
							downloadModels(models);
						}}
					>
						<div class=" self-center mr-2 font-medium line-clamp-1">
							{$i18n.t('Export Presets')}
						</div>

						<div class=" self-center">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="w-3.5 h-3.5"
							>
								<path
									fill-rule="evenodd"
									d="M4 2a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5V6.621a1.5 1.5 0 0 0-.44-1.06L9.94 2.439A1.5 1.5 0 0 0 8.878 2H4Zm4 3.5a.75.75 0 0 1 .75.75v2.69l.72-.72a.75.75 0 1 1 1.06 1.06l-2 2a.75.75 0 0 1-1.06 0l-2-2a.75.75 0 0 1 1.06-1.06l.72.72V6.25A.75.75 0 0 1 8 5.5Z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					</button>
				</div>
			</div>
		{/if}
	{:else}
		<ModelEditor
			edit
			model={models.find((m) => m.id === selectedModelId)}
			preset={false}
			onSubmit={(model) => {
				console.log(model);
				upsertModelHandler(model);
				selectedModelId = null;
			}}
			onBack={() => {
				selectedModelId = null;
			}}
		/>
	{/if}
{:else}
	<div class=" h-full w-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}

<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { getSessionUser } from '$lib/apis/auths';
	import { trackUserRegisteredWithAuth0, trackUserLoggedInWithAuth0 } from '$lib/services/analytics';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';

	// Import the new components
	import VideoBackground from '$lib/components/auth/VideoBackground.svelte';
	import FrostedCard from '$lib/components/auth/FrostedCard.svelte';
	import ChannelLogo from '$lib/components/auth/ChannelLogo.svelte';
	import AnimatedLogo from '$lib/components/auth/AnimatedLogo.svelte';
	import FeatureSlider from '$lib/components/auth/FeatureSlider.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let authError: string | null = null;
	let isDarkMode = false;
	
	// Feature slides data with more interesting Channel-related content
	const featureSlides = [
		{ 
			title: 'One Place for All AI Assistants',
			description: 'Connect with the best AI models and assistants through a single, unified interface',
			image: `${WEBUI_BASE_URL}/static/splash.png` 
		},
		{ 
			title: 'Powerful Conversations',
			description: 'Engage in natural conversations with multiple AI models',
			image: `${WEBUI_BASE_URL}/static/splash.png` 
		},
		{ 
			title: 'Customizable Experience',
			description: 'Configure models and settings to match your specific needs',
			image: `${WEBUI_BASE_URL}/static/splash.png` 
		},
		{ 
			title: 'Privacy First',
			description: 'Your conversations stay private and secure',
			image: `${WEBUI_BASE_URL}/static/splash.png` 
		}
	];

	const querystringValue = (key) => {
		const querystring = window.location.search;
		const urlParams = new URLSearchParams(querystring);
		return urlParams.get(key);
	};

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t('You\'re now logged in.'));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			// Track auth event based on the source
			const isAuth0Login = $page.url.search.includes('token') || $page.url.hash.includes('token');
			
			if (isAuth0Login) {
				// User logged in or registered with Auth0
				if (sessionUser.is_new_user) {
					trackUserRegisteredWithAuth0(sessionUser.id);
				} else {
					trackUserLoggedInWithAuth0(sessionUser.id);
				}
			}

			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
	};

	const checkOauthCallback = async () => {
		// Check for token in URL search params
		const urlParams = new URLSearchParams(window.location.search);
		const token = urlParams.get('token');
		
		if (token) {
			const sessionUser = await getSessionUser(token).catch((error) => {
				toast.error(`${error}`);
				return null;
			});
			if (!sessionUser) {
				return;
			}
			localStorage.token = token;
			await setSessionUser(sessionUser);
		} else if (!$page.url.hash) {
			return;
		}
		
		// Check for token in URL hash fragment
		const hash = $page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		
		const params = new URLSearchParams(hash);
		const hashToken = params.get('token');
		
		if (!hashToken) {
			return;
		}
		
		const sessionUser = await getSessionUser(hashToken).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!sessionUser) {
			return;
		}
		localStorage.token = hashToken;
		await setSessionUser(sessionUser);
	};

	onMount(async () => {
		// Check for logout parameter first - this will force a logout regardless of current state
		const logoutParam = querystringValue('logout');
		if (logoutParam === 'true') {
			console.log('Forced logout detected, clearing auth data');
			// Clear all auth-related data
			localStorage.removeItem('token');
			localStorage.removeItem('oauth_id_token');
			
			// Reset the user store
			await user.set(undefined);
			
			// Show success message
			toast.success($i18n.t('You have been logged out'));
			
			// Clean up the URL to remove the logout parameter
			// This prevents reload loops if user refreshes the page
			const url = new URL(window.location.href);
			url.searchParams.delete('logout');
			window.history.replaceState({}, '', url);
			
			// Force reload the page to ensure a clean state
			// But only after a brief timeout to allow toast to show
			setTimeout(() => {
				window.location.href = '/auth';
			}, 500);
			
			// Return early to prevent other initialization
			return;
		}
		
		if ($user !== undefined) {
			await goto('/');
		}
		
		console.log("Auth page loaded. URL search:", window.location.search);
		console.log("Auth page loaded. URL hash:", window.location.hash);
		
		// Check for error parameter in URL
		const errorParam = querystringValue('error');
		if (errorParam) {
			authError = decodeURIComponent(errorParam);
			console.error('Auth error detected:', authError);
		} else {
			console.log('No error parameter in URL');
			authError = null;
		}
		
		// Detect dark mode based on user preference
		const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
		isDarkMode = prefersDarkMode;
		
		// Listen for theme changes
		const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
		darkModeMediaQuery.addEventListener('change', (e) => {
			isDarkMode = e.matches;
		});
		
		await checkOauthCallback();
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

{#if loaded}
	<!-- Main container where scrolling happens -->
	<div class="h-[100dvh] overflow-auto">
		<!-- Inner content wrapper that allows vertical stacking on mobile -->
		<div class="w-full min-h-[100dvh] flex flex-col md:flex-row">
			<!-- Logo positioned consistently across all screen sizes -->
			<div class="fixed top-8 left-8 z-20">
				<ChannelLogo onClick={() => goto('/')} />
			</div>

			<!-- Left pane - Login form with video background -->
			<div class="w-full md:w-1/2 h-[100dvh] flex items-center justify-center relative">
				<div class="absolute inset-0 overflow-hidden -z-10">
					<VideoBackground />
				</div>

				<FrostedCard className="w-full max-w-md mx-6">
					<div class="p-6">
						<div class="text-left mb-6">
							<h1 class="text-3xl font-bold">{$WEBUI_NAME}</h1>
							<p class="mt-4 text-xs text-gray-600" style="font-weight: 300;">
								{$i18n.t('Connect with all the top AI assistants in one place.')}
							</p>
						</div>

						<div class="space-y-4">
							{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
								<div class="flex items-center justify-center gap-3 text-xl text-center font-semibold">
									<div>
										{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}
									</div>
									<div>
										<Spinner />
									</div>
								</div>
							{:else if $config?.oauth?.providers?.auth0}
								<!-- Single Sign In Button -->
								<button 
									class="w-full bg-black hover:bg-black/90 text-white rounded-full font-medium py-2.5 px-4 flex justify-center items-center"
									on:click={() => {
										// Create the Auth0 login URL with the frontend origin and port explicitly encoded in the state
										const frontendOrigin = encodeURIComponent(window.location.origin);
										
										// Set the returnTo URL to the current origin + /auth to ensure we return to the frontend
										const returnToUrl = encodeURIComponent(`${window.location.origin}/auth`);
										
										// Redirect to the Auth0 login endpoint with the frontend origin
										window.location.href = `/api/v1/auths/oauth/auth0/login?frontendOrigin=${frontendOrigin}&returnTo=${returnToUrl}`;
									}}
								>
									Sign In
								</button>
							{/if}

							{#if authError}
								<div class="text-red-500 text-xs mt-2 text-center">
									{authError}
								</div>
							{/if}

							<p class="text-xs text-center text-gray-600 mt-4">
								Sign up via the Channel mobile app
							</p>
						</div>
					</div>
				</FrostedCard>
			</div>

			<!-- Right pane - Feature showcase -->
			<div class="w-full md:w-1/2 bg-[#E4E6E9] h-[100dvh] flex items-center justify-center p-6">
				<div class="w-full max-w-[52rem] overflow-hidden rounded-lg bg-white/30 backdrop-blur-xl backdrop-filter shadow-lg border border-white/20 h-[85vh] relative">
					<div class="p-8 h-full flex flex-col items-center justify-center">
						<div class="flex-grow w-full flex items-center justify-center">
							<!-- Feature slider component -->
							<FeatureSlider slides={featureSlides} />
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
{:else}
	<div class="flex items-center justify-center min-h-screen bg-white dark:bg-black">
		<div class="flex flex-col items-center">
			<AnimatedLogo />
			<div class="mt-4">
				<Spinner />
			</div>
		</div>
	</div>
{/if}

import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';
import path from 'path';

import { viteStaticCopy } from 'vite-plugin-static-copy';

// /** @type {import('vite').Plugin} */
// const viteServerConfig = {
// 	name: 'log-request-middleware',
// 	configureServer(server) {
// 		server.middlewares.use((req, res, next) => {
// 			res.setHeader('Access-Control-Allow-Origin', '*');
// 			res.setHeader('Access-Control-Allow-Methods', 'GET');
// 			res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
// 			res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
// 			next();
// 		});
// 	}
// };

export default defineConfig(({ mode }) => {
	// Load env variables based on mode
	const env = loadEnv(mode, process.cwd(), '');
	
	// Get frontend port from env or use default
	const frontendPort = parseInt(env.VITE_PORT || '5173');
	
	// Get backend URL from env or use default
	// Explicitly use IPv4 (127.0.0.1) instead of localhost to avoid IPv6 issues
	const backendHost = env.VITE_API_HOST || '127.0.0.1';
	const backendPort = parseInt(env.OPEN_WEBUI_PORT || '8080');
	const backendUrl = `http://${backendHost}:${backendPort}`;
	
	console.log(`[vite] Proxying API requests to: ${backendUrl}`);
	
	return {
		plugins: [
			sveltekit(),
			viteStaticCopy({
				targets: [
					{
						src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

						dest: 'wasm'
					}
				]
			})
		],
		define: {
			APP_VERSION: JSON.stringify(process.env.npm_package_version),
			APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
		},
		resolve: {
			alias: {
				$custom: path.resolve('./src/custom')
			}
		},
		build: {
			sourcemap: true
		},
		worker: {
			format: 'es'
		},
		server: {
			port: frontendPort,
			host: true,
			strictPort: true, // This prevents port switching
			proxy: {
				'/api': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
					configure: (proxy, _options) => {
						proxy.on('error', (err, _req, _res) => {
							console.log('proxy error', err);
						});
						proxy.on('proxyReq', (proxyReq, req, _res) => {
							console.log('Sending Request:', req.method, req.url);
						});
						proxy.on('proxyRes', (proxyRes, req, _res) => {
							console.log('Received Response:', proxyRes.statusCode, req.url);
						});
					},
					rewrite: (path) => path,
				},
				// Make sure we handle the specific Auth0 callback route explicitly
				'/api/v1/auths/oauth/auth0/callback': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
				}
			}
		}
	};
});

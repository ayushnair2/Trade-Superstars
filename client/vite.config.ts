import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const BACKEND = 'http://localhost:8000'

// One rule. Every FastAPI route is mounted under /api, so adding a backend
// router needs no change here -- which is the point: the old per-prefix list
// had to be remembered, and five separate times it was not.
const API_PREFIX = '/api'

/** Catch a call that forgot the /api prefix.
 *
 * The single proxy rule means anything under /api reaches the backend, even an
 * unknown path, which answers with the backend's own JSON 404. What it cannot
 * catch is client code calling '/market/prices' directly instead of going
 * through api(): that still falls through to the SPA and returns index.html
 * with a 200, which surfaces far away as a JSON parse error.
 *
 * This app has no client-side router -- every view is React state on one page
 * -- so '/' is the only legitimate navigation. Anything else that is not /api,
 * not a Vite internal and not a file is a bypassed API call, and gets a 502
 * naming the fix instead of silence.
 */
function apiPrefixGuard(): Plugin {
  return {
    name: 'api-prefix-guard',
    apply: 'serve',
    configureServer(server) {
      // Registered BEFORE the internal middlewares, deliberately. Registering
      // after them (by returning a function) never fires: Vite's SPA fallback
      // has already sent index.html by then, which is why the previous version
      // of this guard was silent every time the proxy list was missing a root.
      // Running first is safe because everything this does not 502 is passed
      // straight on with next(), including /api, which the proxy handles.
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0]
        const isRoot = url === '/' || url === ''
        const isApi = url === API_PREFIX || url.startsWith(`${API_PREFIX}/`)
        const isViteInternal =
          url.startsWith('/@') ||
          url.startsWith('/node_modules') ||
          url.startsWith('/__') ||
          url.startsWith('/src/')
        const isFile = /\.[a-z0-9]+$/i.test(url)

        if (isRoot || isApi || isViteInternal || isFile) return next()

        res.statusCode = 502
        res.setHeader('Content-Type', 'application/json')
        res.end(
          JSON.stringify({
            detail:
              `'${url}' fell through to the SPA. Backend routes live under ` +
              `${API_PREFIX}; call it through api() in src/api.ts rather than ` +
              `fetching the bare path.`,
          }),
        )
      })
    },
  }
}

// App code calls relative paths through api() (/api/market/prices); the proxy
// forwards them to FastAPI so there is no hardcoded host in the client.
export default defineConfig({
  plugins: [react(), apiPrefixGuard()],
  server: {
    proxy: {
      [API_PREFIX]: { target: BACKEND, changeOrigin: true },
    },
  },
})

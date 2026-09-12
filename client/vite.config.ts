import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const BACKEND = 'http://localhost:8000'

// Every top-level route group served by FastAPI. Adding a backend router means
// adding its prefix here -- and only here. Vite treats a key starting with "^"
// as a regex, so this is one proxy rule covering all of them.
const API_ROOTS = [
  'auth',
  'market',
  'portfolio',
  'athletes',
  'lessons',
  'settings',
  'funds',
]
const API_PATTERN = `^/(${API_ROOTS.join('|')})(/|$)`

/** Make an unproxied API call fail loudly.
 *
 * Anything that reaches the SPA fallback gets index.html with a 200, so a
 * missing proxy entry used to look like a JSON parse error somewhere far away.
 * This runs after Vite's own middlewares -- proxied requests never get here --
 * and turns that silence into a 502 that names the fix.
 */
function apiFallbackGuard(): Plugin {
  return {
    name: 'api-fallback-guard',
    apply: 'serve',
    configureServer(server) {
      // returning a function registers this AFTER the internal middlewares,
      // including the proxy
      return () => {
        server.middlewares.use((req, res, next) => {
          const url = (req.url ?? '').split('?')[0]
          const accepts = req.headers.accept ?? ''
          const looksLikeApi =
            req.method !== 'GET' || accepts.includes('application/json')
          const isViteInternal = url.startsWith('/@') || url.startsWith('/node_modules')
          const isFile = /\.[a-z0-9]+$/i.test(url)

          if (!looksLikeApi || isViteInternal || isFile) return next()

          res.statusCode = 502
          res.setHeader('Content-Type', 'application/json')
          res.end(
            JSON.stringify({
              detail:
                `'${url}' was not proxied to the backend, so it fell through to ` +
                `the SPA. Add its top-level prefix to API_ROOTS in vite.config.ts.`,
            }),
          )
        })
      }
    },
  }
}

// App code calls relative paths (/market/prices); the proxy forwards them to
// the FastAPI backend so there is no hardcoded host in the client.
export default defineConfig({
  plugins: [react(), apiFallbackGuard()],
  server: {
    proxy: {
      [API_PATTERN]: { target: BACKEND, changeOrigin: true },
    },
  },
})

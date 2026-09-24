// Empty in dev so requests stay relative and the Vite proxy handles them; set
// to the deployed backend ORIGIN in production, with no path -- the /api
// prefix below is the app's, not the deployment's (see client/.env.example).
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const TOKEN_KEY = 'ts.token'

/** Every backend route is mounted under /api, so callers pass the bare path
 *  ('/market/prices') and the prefix is added in exactly one place. */
export const api = (path: string) => `${BASE}/api${path}`

// localStorage throws in some contexts (private mode, blocked site data), so
// every access is guarded.
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY)
    else localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // not persisting is survivable; the session still works in memory
  }
}

/** fetch with the bearer token attached when we have one.
 *  Public endpoints ignore it; protected ones need it. One place to change. */
export function authFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(api(path), { ...init, headers })
}

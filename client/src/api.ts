// Empty in dev so requests stay relative and the Vite proxy handles them; set
// to the deployed backend URL in production (see client/.env.example).
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export const api = (path: string) => `${BASE}${path}`

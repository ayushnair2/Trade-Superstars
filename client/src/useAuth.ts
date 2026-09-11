import { useCallback, useEffect, useState } from 'react'

import { authFetch, setToken } from './api'

export type AuthUser = { id?: number; email: string }

export type Auth = {
  user: AuthUser | null
  /** true until the stored token has been checked, so the UI can hold off */
  checking: boolean
  login: (email: string, password: string) => Promise<string | null>
  signup: (email: string, password: string) => Promise<string | null>
  logout: () => void
}

async function errorFrom(res: Response): Promise<string> {
  const body = await res.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  // FastAPI validation errors come back as a list of objects
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  return `request failed (${res.status})`
}

export function useAuth(): Auth {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checking, setChecking] = useState(true)

  // validate any stored token once on load
  useEffect(() => {
    let cancelled = false
    authFetch('/auth/me')
      .then(async (res) => {
        if (cancelled) return
        if (res.ok) setUser(await res.json())
        else if (res.status === 401) setToken(null) // stale or expired
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const submit = useCallback(
    async (path: string, email: string, password: string) => {
      try {
        const res = await authFetch(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!res.ok) return await errorFrom(res)
        const data = await res.json()
        setToken(data.access_token)
        setUser({ email: data.email })
        return null
      } catch {
        return 'could not reach the server'
      }
    },
    [],
  )

  return {
    user,
    checking,
    login: useCallback((e, p) => submit('/auth/login', e, p), [submit]),
    signup: useCallback((e, p) => submit('/auth/signup', e, p), [submit]),
    logout: useCallback(() => {
      setToken(null)
      setUser(null)
    }, []),
  }
}

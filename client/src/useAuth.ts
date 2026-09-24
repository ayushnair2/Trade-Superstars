import { useCallback, useEffect, useState } from 'react'

import { authFetch, setToken } from './api'

export type AuthUser = { id?: number; email: string; display_name?: string }

export type Auth = {
  user: AuthUser | null
  /** true until the stored token has been checked, so the UI can hold off */
  checking: boolean
  login: (email: string, password: string) => Promise<string | null>
  signup: (
    email: string,
    password: string,
    displayName?: string,
  ) => Promise<string | null>
  /** null on success, otherwise the message to show inline */
  rename: (displayName: string) => Promise<string | null>
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
    async (path: string, email: string, password: string, displayName?: string) => {
      try {
        const body: Record<string, string> = { email, password }
        // omitted rather than sent empty: the backend assigns trader-<id>
        if (displayName?.trim()) body.display_name = displayName.trim()
        const res = await authFetch(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!res.ok) return await errorFrom(res)
        const data = await res.json()
        setToken(data.access_token)
        setUser({ email: data.email, display_name: data.display_name })
        return null
      } catch {
        return 'could not reach the server'
      }
    },
    [],
  )

  const rename = useCallback(async (displayName: string) => {
    try {
      const res = await authFetch('/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName.trim() }),
      })
      if (!res.ok) return await errorFrom(res)
      setUser(await res.json())
      return null
    } catch {
      return 'could not reach the server'
    }
  }, [])

  return {
    user,
    checking,
    login: useCallback((e, p) => submit('/auth/login', e, p), [submit]),
    signup: useCallback(
      (e, p, d) => submit('/auth/signup', e, p, d),
      [submit],
    ),
    rename,
    logout: useCallback(() => {
      setToken(null)
      setUser(null)
    }, []),
  }
}

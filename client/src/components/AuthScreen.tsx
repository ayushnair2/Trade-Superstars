import { useState } from 'react'

import type { Auth } from '../useAuth'

type Props = {
  auth: Auth
  onClose: () => void
  onSuccess: () => void
}

export default function AuthScreen({ auth, onClose, onSuccess }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const signingUp = mode === 'signup'

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    const message = await (signingUp
      ? auth.signup(email, password)
      : auth.login(email, password))
    setBusy(false)
    if (message) {
      setError(message)
      return
    }
    setError(null)
    onSuccess()
  }

  return (
    <div className="settings-backdrop" onClick={onClose}>
      <form
        className="settings-panel auth-panel"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <button
          type="button"
          className="settings-close"
          onClick={onClose}
          aria-label="Close"
        >
          X
        </button>

        <div className="panel-title">{signingUp ? 'SIGN UP' : 'LOG IN'}</div>

        <label className="auth-label" htmlFor="auth-email">
          EMAIL
        </label>
        <input
          id="auth-email"
          className="auth-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label className="auth-label" htmlFor="auth-password">
          PASSWORD
        </label>
        <input
          id="auth-password"
          className="auth-input"
          type="password"
          autoComplete={signingUp ? 'new-password' : 'current-password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button className="btn buy auth-submit" type="submit" disabled={busy}>
          {signingUp ? 'CREATE ACCOUNT' : 'LOG IN'}
        </button>

        {error && <div className="auth-error">{error}</div>}

        <button
          type="button"
          className="auth-toggle"
          onClick={() => {
            setMode(signingUp ? 'login' : 'signup')
            setError(null)
          }}
        >
          {signingUp ? 'Have an account? Log in' : 'New here? Sign up'}
        </button>
      </form>
    </div>
  )
}

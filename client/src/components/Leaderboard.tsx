import { useCallback, useEffect, useState } from 'react'

import { authFetch } from '../api'
import { changeClass, money } from '../format'
import type { LeaderboardBody, LeaderboardEntry } from '../types'
import type { Auth } from '../useAuth'

type Props = { auth: Auth }

/** Matches LEADERBOARD_CACHE_TTL: the server serves a cached ranking for 30s,
 *  so polling faster only spends requests on the same answer. */
const POLL_MS = 30_000

const pct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`

/** #1 gets the amber accent, #2 and #3 a quieter one. */
const rankClass = (rank: number) =>
  rank === 1 ? ' gold' : rank === 2 ? ' silver' : rank === 3 ? ' bronze' : ''

function Row({ entry, me }: { entry: LeaderboardEntry; me: boolean }) {
  return (
    <tr className={`lb-row${me ? ' mine' : ''}${rankClass(entry.rank)}`}>
      <td className="lb-rank">{entry.rank}</td>
      <td className="lb-name">
        {entry.display_name}
        {me && <span className="lb-you">YOU</span>}
      </td>
      <td className="num">{money(entry.total_value)}</td>
      <td className={`num ${changeClass(entry.return_pct)}`}>{pct(entry.return_pct)}</td>
    </tr>
  )
}

export default function Leaderboard({ auth }: Props) {
  const [board, setBoard] = useState<LeaderboardBody | null>(null)
  const [stale, setStale] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const myName = auth.user?.display_name ?? null

  const load = useCallback(async () => {
    try {
      const res = await authFetch('/leaderboard')
      if (!res.ok) throw new Error(String(res.status))
      setBoard(await res.json())
      setStale(false)
    } catch {
      // keep the last good board; just flag that it is behind
      setStale(true)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [load, myName])

  async function saveName(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    const message = await auth.rename(draft)
    setBusy(false)
    if (message) {
      setError(message)
      return
    }
    setError(null)
    setEditing(false)
    // the server clears its cache on rename, so this shows the new name at once
    load()
  }

  if (!board) {
    return (
      <div className="panel lb-panel">
        <div className="panel-title">LEADERBOARD</div>
        <div className="state">LOADING…</div>
      </div>
    )
  }

  return (
    <div className="panel lb-panel">
      <div className="lb-head">
        <div className="panel-title">LEADERBOARD</div>
        {stale && <div className="reconnecting">RECONNECTING…</div>}
        <div className="lb-count">{board.total_players} players</div>
      </div>

      {myName && (
        <div className="lb-me-bar">
          {editing ? (
            <form className="lb-rename" onSubmit={saveName}>
              <input
                className="auth-input lb-rename-input"
                value={draft}
                autoFocus
                maxLength={20}
                onChange={(e) => setDraft(e.target.value)}
                aria-label="New display name"
              />
              <button className="btn buy lb-rename-save" type="submit" disabled={busy}>
                SAVE
              </button>
              <button
                type="button"
                className="btn lb-rename-cancel"
                onClick={() => {
                  setEditing(false)
                  setError(null)
                }}
              >
                CANCEL
              </button>
            </form>
          ) : (
            <>
              <span className="lb-me-label">YOU ARE</span>
              <span className="lb-me-name">{myName}</span>
              <button
                className="lb-rename-btn"
                onClick={() => {
                  setDraft(myName)
                  setError(null)
                  setEditing(true)
                }}
              >
                RENAME
              </button>
            </>
          )}
        </div>
      )}
      {error && <div className="auth-error lb-error">{error}</div>}

      <div className="lb-scroll">
        <table className="lb-table">
          <thead>
            <tr>
              <th className="lb-rank">#</th>
              <th>PLAYER</th>
              <th className="num">TOTAL VALUE</th>
              <th className="num">RETURN</th>
            </tr>
          </thead>
          <tbody>
            {board.top.map((entry) => (
              <Row
                key={entry.rank}
                entry={entry}
                me={entry.display_name === myName}
              />
            ))}
            {board.me && (
              <>
                {/* they fell outside the slice, so their row is pinned below a
                    divider rather than being absent */}
                <tr className="lb-divider">
                  <td colSpan={4}>···</td>
                </tr>
                <Row entry={board.me} me />
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

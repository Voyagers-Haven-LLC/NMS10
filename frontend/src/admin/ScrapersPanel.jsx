import { useCallback, useEffect, useState } from 'react'
import { apiAuth } from '../api/client'
import { useToast } from '../context/ToastContext'

const SOURCE_LABELS = {
  bluesky: 'Bluesky',
  youtube: 'YouTube',
  reddit: 'Reddit',
  twitter: 'Twitter / X',
  instagram: 'Instagram',
}

function timeAgo(iso) {
  if (!iso) return '—'
  const ts = new Date(iso)
  if (isNaN(ts.getTime())) return iso
  const diff = (Date.now() - ts.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function authPill(state) {
  const cls =
    state === 'ok' ? 'approved' : state === 'auth-failed' ? 'rejected' : 'pending'
  const label =
    state === 'ok' ? 'OK'
      : state === 'auth-failed' ? 'auth failed'
      : 'stub credentials'
  return <span className={`status-pill ${cls}`}>{label}</span>
}

export default function ScrapersPanel() {
  const [rows, setRows] = useState([])
  const [running, setRunning] = useState({})
  const toast = useToast()

  const load = useCallback(() => {
    apiAuth('/admin/scraper-status')
      .then(setRows)
      .catch((e) => toast.error(e.message))
  }, [toast])

  useEffect(() => {
    load()
    const id = setInterval(load, 15000) // auto-refresh
    return () => clearInterval(id)
  }, [load])

  const runNow = async (name) => {
    setRunning((r) => ({ ...r, [name]: true }))
    try {
      const res = await apiAuth(`/admin/scrapers/${name}/run-once`, { method: 'POST' })
      if (res.skipped) {
        toast.info(`${name}: skipped (${res.skipped})`)
      } else if (res.ok) {
        toast.success(
          `${name}: fetched ${res.fetched ?? 0}, inserted ${res.inserted ?? 0}` +
          (res.notified ? `, notified ${res.notified}` : '')
        )
      } else {
        toast.error(`${name}: ${res.error || 'failed'}`)
      }
      load()
    } catch (err) {
      toast.error(`${name}: ${err.message}`)
    } finally {
      setRunning((r) => ({ ...r, [name]: false }))
    }
  }

  if (rows.length === 0) {
    return <div className="empty-state">No scrapers registered yet.</div>
  }

  return (
    <>
      <div className="admin-section-header">
        <h2>Scrapers</h2>
        <button className="btn secondary" onClick={load}>Refresh</button>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Auth</th>
              <th>Last run</th>
              <th>Last success</th>
              <th>Streak</th>
              <th>Runs · success / fail</th>
              <th>Last error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const failingStreak = (r.consecutive_failures || 0) >= 1
              return (
                <tr key={r.name}>
                  <td><strong>{SOURCE_LABELS[r.name] || r.name}</strong></td>
                  <td>{authPill(r.auth_state || 'ok')}</td>
                  <td>{timeAgo(r.last_run)}</td>
                  <td>{timeAgo(r.last_success)}</td>
                  <td style={{ color: failingStreak ? '#ff8a8a' : 'inherit' }}>
                    {r.consecutive_failures || 0}{r.in_backoff ? ' · backoff' : ''}
                  </td>
                  <td style={{ color: 'var(--text-tertiary)' }}>
                    {r.runs || 0} · {r.successes || 0} / {r.failures || 0}
                  </td>
                  <td
                    style={{
                      maxWidth: 280,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      color: r.last_error ? '#ff8a8a' : 'var(--text-tertiary)',
                    }}
                    title={r.last_error || ''}
                  >
                    {r.last_error || '—'}
                  </td>
                  <td className="actions">
                    <button
                      type="button"
                      className="btn small primary"
                      disabled={!!running[r.name]}
                      onClick={() => runNow(r.name)}
                    >
                      {running[r.name] ? 'Running…' : 'Run Now'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem', marginTop: '1rem' }}>
        Auto-refreshing every 15 seconds. Stub-credentials means the env var
        is missing or set to "STUB" — the scheduler still runs, but the scraper
        no-ops until real credentials land.
      </p>
    </>
  )
}

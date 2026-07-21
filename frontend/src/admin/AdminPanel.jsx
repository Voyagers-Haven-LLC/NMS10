import { useCallback, useEffect, useState } from 'react'
import { apiAuth } from '../api/client'
import Modal from '../components/Modal'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import BaseEditor from './BaseEditor'
import CommunityEditor from './CommunityEditor'
import MeetupEditor from './MeetupEditor'
import SocialEditor from './SocialEditor'
import ScrapersPanel from './ScrapersPanel'

const TABS = [
  { id: 'queue', label: 'Queue' },
  { id: 'bases', label: 'Bases' },
  { id: 'communities', label: 'Communities' },
  { id: 'meetups', label: 'Meetups' },
  { id: 'socials', label: 'Socials' },
  { id: 'scrapers', label: 'Scrapers' },
]

function ActionBtn({ kind = 'secondary', children, ...props }) {
  return (
    <button type="button" className={`btn small ${kind}`} {...props}>
      {children}
    </button>
  )
}

function QueueTab({ refreshTick, onAfterAction }) {
  const [queue, setQueue] = useState({ bases: [], communities: [], meetups: [], socials: [] })
  const toast = useToast()

  const load = useCallback(() => {
    apiAuth('/admin/queue')
      .then(setQueue)
      .catch((e) => toast.error(e.message))
  }, [toast])

  useEffect(load, [load, refreshTick])

  const queueAction = async (kind, id, action) => {
    try {
      await apiAuth(`/admin/${kind}/${id}/${action}`, { method: 'POST' })
      toast.success(`${action} ${id}`)
      load()
      onAfterAction?.()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const total =
    queue.bases.length +
    queue.communities.length +
    queue.meetups.length +
    (queue.socials?.length ?? 0)

  if (total === 0) {
    return <div className="empty-state">Queue is empty. Nothing pending. ✨</div>
  }

  return (
    <>
      {queue.bases.length > 0 && (
        <div className="queue-group">
          <div className="queue-group-title">Pending bases ({queue.bases.length})</div>
          <div className="admin-table-wrap"><table className="admin-table">
            <thead><tr><th>Photo</th><th>Title</th><th>Builder</th><th>Platform</th><th>Submitted</th><th>Actions</th></tr></thead>
            <tbody>
              {queue.bases.map((b) => (
                <tr key={b.id}>
                  <td>
                    {b.hero_image_path ? (
                      <a className="queue-thumb" href={b.hero_image_path} target="_blank" rel="noreferrer" title="Open full size">
                        <img src={b.hero_image_path} alt="" />
                      </a>
                    ) : (
                      <div className="queue-thumb empty">no&nbsp;photo</div>
                    )}
                    {b.image_count > 0 && <div className="field-hint" style={{ marginTop: 2 }}>+{b.image_count} more</div>}
                  </td>
                  <td>{b.title}</td>
                  <td>{b.builder_name}</td>
                  <td>{b.platform || '—'}</td>
                  <td>{b.submitted_at}</td>
                  <td className="actions">
                    <ActionBtn kind="primary" onClick={() => queueAction('bases', b.id, 'approve')}>Approve</ActionBtn>
                    <ActionBtn kind="danger" onClick={() => queueAction('bases', b.id, 'reject')}>Reject</ActionBtn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
      {queue.communities.length > 0 && (
        <div className="queue-group">
          <div className="queue-group-title">Pending communities ({queue.communities.length})</div>
          <div className="admin-table-wrap"><table className="admin-table">
            <thead><tr><th>Logo</th><th>Name</th><th>Language</th><th>Added</th><th>Actions</th></tr></thead>
            <tbody>
              {queue.communities.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.logo_image_path ? (
                      <a className="queue-thumb" href={c.logo_image_path} target="_blank" rel="noreferrer" title="Open full size">
                        <img src={c.logo_image_path} alt="" />
                      </a>
                    ) : (
                      <div className="queue-thumb empty">no&nbsp;logo</div>
                    )}
                  </td>
                  <td>{c.name}</td>
                  <td>{c.language || '—'}</td>
                  <td>{c.added_at}</td>
                  <td className="actions">
                    <ActionBtn kind="primary" onClick={() => queueAction('communities', c.id, 'approve')}>Approve</ActionBtn>
                    <ActionBtn kind="danger" onClick={() => queueAction('communities', c.id, 'reject')}>Reject</ActionBtn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
      {queue.meetups.length > 0 && (
        <div className="queue-group">
          <div className="queue-group-title">Pending meetups ({queue.meetups.length})</div>
          <div className="admin-table-wrap"><table className="admin-table">
            <thead><tr><th>Title</th><th>Region</th><th>Location</th><th>Submitted</th><th>Actions</th></tr></thead>
            <tbody>
              {queue.meetups.map((m) => (
                <tr key={m.id}>
                  <td>{m.title}</td>
                  <td>{m.region || '—'}</td>
                  <td>{m.location || '—'}</td>
                  <td>{m.submitted_at}</td>
                  <td className="actions">
                    <ActionBtn kind="primary" onClick={() => queueAction('meetups', m.id, 'approve')}>Approve</ActionBtn>
                    <ActionBtn kind="danger" onClick={() => queueAction('meetups', m.id, 'reject')}>Reject</ActionBtn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
      {queue.socials?.length > 0 && (
        <div className="queue-group">
          <div className="queue-group-title">Pending social posts ({queue.socials.length})</div>
          <div className="admin-table-wrap"><table className="admin-table">
            <thead><tr><th>Source</th><th>Author</th><th>Content</th><th>Fetched</th><th>Actions</th></tr></thead>
            <tbody>
              {queue.socials.map((s) => (
                <tr key={s.id}>
                  <td><span className={`source-badge ${s.source}`}>{s.source}</span></td>
                  <td>{s.author_name || s.author_handle || '—'}</td>
                  <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.content || ''}>
                    {s.external_url
                      ? <a href={s.external_url} target="_blank" rel="noreferrer">{(s.content || '').slice(0, 80) || s.external_url}</a>
                      : (s.content || '').slice(0, 80)}
                  </td>
                  <td>{s.fetched_at}</td>
                  <td className="actions">
                    <ActionBtn kind="primary" onClick={() => queueAction('socials', s.id, 'approve')}>Approve</ActionBtn>
                    <ActionBtn kind="danger" onClick={() => queueAction('socials', s.id, 'reject')}>Reject</ActionBtn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
    </>
  )
}

function EntityTab({ kind, columns, render, EditorComponent, onChanged }) {
  const [items, setItems] = useState([])
  const [editing, setEditing] = useState(null) // null | 'new' | item
  const toast = useToast()

  const load = useCallback(() => {
    apiAuth(`/admin/${kind}`)
      .then(setItems)
      .catch((e) => toast.error(e.message))
  }, [kind, toast])
  useEffect(load, [load])

  const remove = async (item) => {
    if (!confirm(`Delete ${item.title || item.name || item.id}? This is permanent.`)) return
    try {
      await apiAuth(`/admin/${kind}/${item.id}`, { method: 'DELETE' })
      toast.success(`Deleted.`)
      load()
      onChanged?.()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <div className="admin-section-header">
        <h2>{kind}</h2>
        <button className="btn primary" onClick={() => setEditing('new')}>+ Add new</button>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">No {kind} yet.</div>
      ) : (
        <div className="admin-table-wrap"><table className="admin-table">
          <thead><tr>{columns.map((c) => (<th key={c.key}>{c.label}</th>))}<th>Actions</th></tr></thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id}>
                {columns.map((c) => (<td key={c.key}>{render(it, c.key)}</td>))}
                <td className="actions">
                  <ActionBtn onClick={() => setEditing(it)}>Edit</ActionBtn>
                  <ActionBtn kind="danger" onClick={() => remove(it)}>Delete</ActionBtn>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}

      <Modal
        open={!!editing}
        title={editing === 'new' ? `New ${kind.slice(0, -1)}` : `Edit ${editing?.title || editing?.name || editing?.id || ''}`}
        onClose={() => setEditing(null)}
        wide={kind === 'bases' || kind === 'meetups'}
      >
        {editing && (
          <EditorComponent
            id={editing === 'new' ? null : editing.id}
            baseId={editing === 'new' ? null : editing.id}
            existing={editing === 'new' ? null : editing}
            onClose={() => setEditing(null)}
            onSaved={() => {
              setEditing(null)
              load()
              onChanged?.()
            }}
          />
        )}
      </Modal>
    </>
  )
}

export default function AdminPanel() {
  const { username, logout } = useAuth()
  const [tab, setTab] = useState('queue')
  const [queueCount, setQueueCount] = useState(0)
  const [refreshTick, setRefreshTick] = useState(0)
  const toast = useToast()

  const refreshQueueCount = useCallback(() => {
    apiAuth('/admin/queue')
      .then((q) => setQueueCount(q.bases.length + q.communities.length + q.meetups.length + (q.socials?.length ?? 0)))
      .catch(() => {})
  }, [])

  useEffect(refreshQueueCount, [refreshQueueCount, refreshTick])
  const triggerRefresh = () => setRefreshTick((n) => n + 1)

  return (
    <div className="container admin-shell">
      <div className="admin-section-header">
        <h2 style={{ fontFamily: 'var(--font-display)' }}>Admin · {username}</h2>
        <button className="btn secondary" onClick={() => { logout(); toast.info('Signed out.') }}>
          Logout
        </button>
      </div>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`admin-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === 'queue' && queueCount > 0 && <span className="badge">{queueCount}</span>}
          </button>
        ))}
      </div>

      {tab === 'queue' && <QueueTab refreshTick={refreshTick} onAfterAction={triggerRefresh} />}

      {tab === 'bases' && (
        <EntityTab
          kind="bases"
          columns={[
            { key: 'title', label: 'Title' },
            { key: 'builder_name', label: 'Builder' },
            { key: 'platform', label: 'Platform' },
            { key: 'status', label: 'Status' },
            { key: 'view_count', label: 'Views' },
            { key: 'star_count', label: 'Stars' },
          ]}
          render={(it, key) => {
            if (key === 'status')
              return <span className={`status-pill ${it.status}`}>{it.status}</span>
            return it[key] ?? '—'
          }}
          EditorComponent={BaseEditor}
          onChanged={triggerRefresh}
        />
      )}

      {tab === 'communities' && (
        <EntityTab
          kind="communities"
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'language', label: 'Language' },
            { key: 'approved', label: 'Approved' },
          ]}
          render={(it, key) => {
            if (key === 'approved') return it.approved ? '✓' : '—'
            return it[key] ?? '—'
          }}
          EditorComponent={CommunityEditor}
          onChanged={triggerRefresh}
        />
      )}

      {tab === 'meetups' && (
        <EntityTab
          kind="meetups"
          columns={[
            { key: 'title', label: 'Title' },
            { key: 'region', label: 'Region' },
            { key: 'location', label: 'Location' },
            { key: 'starts_at', label: 'Starts' },
            { key: 'approved', label: 'Approved' },
          ]}
          render={(it, key) => {
            if (key === 'approved') return it.approved ? '✓' : '—'
            return it[key] ?? '—'
          }}
          EditorComponent={MeetupEditor}
          onChanged={triggerRefresh}
        />
      )}

      {tab === 'socials' && (
        <EntityTab
          kind="socials"
          columns={[
            { key: 'source', label: 'Source' },
            { key: 'author_name', label: 'Author' },
            { key: 'content', label: 'Content' },
            { key: 'featured', label: 'Featured' },
            { key: 'hidden', label: 'Hidden' },
          ]}
          render={(it, key) => {
            if (key === 'featured') return it.featured ? '★' : '—'
            if (key === 'hidden') return it.hidden ? 'hidden' : '—'
            if (key === 'content') return (it.content || '').slice(0, 80)
            return it[key] ?? '—'
          }}
          EditorComponent={SocialEditor}
          onChanged={triggerRefresh}
        />
      )}

      {tab === 'scrapers' && <ScrapersPanel />}
    </div>
  )
}

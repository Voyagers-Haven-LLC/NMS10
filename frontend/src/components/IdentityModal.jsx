import { useEffect, useState } from 'react'
import Modal from './Modal'
import { useIdentity } from '../context/IdentityContext'
import { useToast } from '../context/ToastContext'
import { RACES, PLATFORMS, SIGILS, blankDraft } from '../identity/identityStorage'

export default function IdentityModal({ open, onClose }) {
  const { identity, setIdentity } = useIdentity()
  const toast = useToast()
  const [draft, setDraft] = useState(() => identity || blankDraft())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // When the modal re-opens, snap the draft back to whatever's currently saved
  // (or blank if nothing). Prevents stale state from a previous open session.
  useEffect(() => {
    if (open) {
      setDraft(identity || blankDraft())
      setError(null)
    }
  }, [open, identity])

  const onChange = (key) => (e) => {
    const v = e.target.type === 'number' || e.target.tagName === 'SELECT' ? Number(e.target.value) : e.target.value
    setDraft((d) => ({ ...d, [key]: v }))
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!draft.name || !draft.name.trim()) {
      setError('Name is required')
      return
    }
    setSaving(true)
    try {
      setIdentity(draft)
      toast.success(`Hello, Traveler ${draft.name.trim()}.`)
      onClose()
    } catch (err) {
      setError(err.message || 'could not save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} title="Your Traveler Identity" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="form-field span-2">
            <label>Name *</label>
            <input
              required
              maxLength={50}
              value={draft.name}
              onChange={onChange('name')}
              autoFocus
              placeholder="What other Travelers should call you"
            />
          </div>

          <div className="form-field">
            <label>Race</label>
            <select value={draft.race} onChange={onChange('race')}>
              {RACES.map((r, i) => (
                <option key={r} value={i}>{r}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label>Platform</label>
            <select value={draft.platform} onChange={onChange('platform')}>
              {PLATFORMS.map((p, i) => (
                <option key={p} value={i}>{p}</option>
              ))}
            </select>
          </div>

          <div className="form-field span-2">
            <label>Sigil</label>
            <select value={draft.sigil} onChange={onChange('sigil')}>
              {SIGILS.map((s, i) => (
                s ? <option key={s} value={i}>{s}</option> : null
              ))}
            </select>
          </div>

          <div className="form-field span-2">
            <label>Affiliation</label>
            <input
              maxLength={60}
              value={draft.affiliation}
              onChange={onChange('affiliation')}
            />
          </div>

          <div className="form-field span-2" style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
            Used to pre-fill submission forms and personalize your Dreaming
            Traveler Card. Stored locally on this device only — nothing is
            sent to a server.
          </div>

          {error && (
            <div className="form-field span-2" style={{ color: '#ff8a8a', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}
        </div>

        <div className="form-actions">
          <button type="button" className="btn secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

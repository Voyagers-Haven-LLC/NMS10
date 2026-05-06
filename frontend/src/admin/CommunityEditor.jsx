import { useEffect, useState } from 'react'
import { apiAuth } from '../api/client'
import { useToast } from '../context/ToastContext'

export default function CommunityEditor({ id, onClose, onSaved }) {
  const isNew = !id
  const [form, setForm] = useState(null)
  const toast = useToast()

  useEffect(() => {
    if (isNew) {
      setForm({ name: '', language: '', description: '', link_url: '', approved: true })
      return
    }
    apiAuth('/admin/communities')
      .then((all) => setForm(all.find((c) => c.id === id)))
      .catch((e) => toast.error(e.message))
  }, [id, isNew, toast])

  if (!form) return <div className="empty-state">Loading…</div>

  const onChange = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    const payload = {
      name: form.name,
      language: form.language || null,
      description: form.description || null,
      link_url: form.link_url || null,
      approved: !!form.approved,
    }
    try {
      const res = isNew
        ? await apiAuth('/admin/communities', { method: 'POST', body: payload })
        : await apiAuth(`/admin/communities/${id}`, { method: 'PUT', body: payload })
      toast.success(`Saved ${res.id}.`)
      onSaved?.(res)
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <form onSubmit={save}>
      <div className="form-grid">
        <div className="form-field span-2">
          <label>Name *</label>
          <input required value={form.name} onChange={onChange('name')} />
        </div>
        <div className="form-field">
          <label>Language</label>
          <input value={form.language || ''} onChange={onChange('language')} />
        </div>
        <div className="form-field">
          <label>Link</label>
          <input value={form.link_url || ''} onChange={onChange('link_url')} />
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description || ''} onChange={onChange('description')} />
        </div>
        <div className="form-field span-2">
          <label>
            <input type="checkbox" checked={!!form.approved} onChange={onChange('approved')} /> Approved (visible publicly)
          </label>
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn primary">{isNew ? 'Create' : 'Save'}</button>
      </div>
    </form>
  )
}

import { useState } from 'react'
import { apiAuth } from '../api/client'
import { useToast } from '../context/ToastContext'

export default function SocialEditor({ existing, onClose, onSaved }) {
  const isNew = !existing
  const [form, setForm] = useState(
    existing || {
      source: 'twitter',
      external_id: '',
      author_name: '',
      author_handle: '',
      content: '',
      external_url: '',
      posted_at: '',
      media_path: '',
      featured: false,
      hidden: false,
    }
  )
  const toast = useToast()
  const onChange = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    const payload = {
      source: form.source,
      external_id: form.external_id,
      author_name: form.author_name || null,
      author_handle: form.author_handle || null,
      content: form.content || null,
      external_url: form.external_url || null,
      posted_at: form.posted_at || null,
      media_path: form.media_path || null,
      featured: !!form.featured,
      hidden: !!form.hidden,
    }
    try {
      const res = isNew
        ? await apiAuth('/admin/socials', { method: 'POST', body: payload })
        : await apiAuth(`/admin/socials/${existing.id}`, { method: 'PUT', body: payload })
      toast.success('Saved.')
      onSaved?.(res)
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <form onSubmit={save}>
      <div className="form-grid">
        <div className="form-field">
          <label>Source</label>
          <select value={form.source} onChange={onChange('source')}>
            {['twitter', 'bluesky', 'youtube', 'reddit', 'tiktok', 'discord'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label>External ID *</label>
          <input required value={form.external_id || ''} onChange={onChange('external_id')} />
        </div>
        <div className="form-field">
          <label>Author name</label>
          <input value={form.author_name || ''} onChange={onChange('author_name')} />
        </div>
        <div className="form-field">
          <label>Author handle</label>
          <input value={form.author_handle || ''} onChange={onChange('author_handle')} />
        </div>
        <div className="form-field span-2">
          <label>Content</label>
          <textarea value={form.content || ''} onChange={onChange('content')} />
        </div>
        <div className="form-field">
          <label>External URL</label>
          <input value={form.external_url || ''} onChange={onChange('external_url')} />
        </div>
        <div className="form-field">
          <label>Posted at (ISO)</label>
          <input value={form.posted_at || ''} onChange={onChange('posted_at')} />
        </div>
        <div className="form-field span-2">
          <label>Media URL</label>
          <input value={form.media_path || ''} onChange={onChange('media_path')} />
        </div>
        <div className="form-field">
          <label>
            <input type="checkbox" checked={!!form.featured} onChange={onChange('featured')} /> Featured
          </label>
        </div>
        <div className="form-field">
          <label>
            <input type="checkbox" checked={!!form.hidden} onChange={onChange('hidden')} /> Hidden
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

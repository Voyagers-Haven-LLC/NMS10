import { useEffect, useState } from 'react'
import { apiAuth, getToken } from '../api/client'
import { useToast } from '../context/ToastContext'

const PLATFORMS = ['pc', 'ps', 'xbox', 'switch']
const STATUSES = ['pending', 'approved', 'rejected']

export default function BaseEditor({ baseId, onClose, onSaved }) {
  const isNew = !baseId
  const [form, setForm] = useState(null)
  const toast = useToast()

  useEffect(() => {
    if (isNew) {
      setForm({
        title: '',
        builder_name: '',
        builder_affiliation: '',
        description: '',
        builder_notes: '',
        platform: 'pc',
        galaxy: '',
        region: '',
        portal_address: '',
        tags: [],
        star_count: 0,
        view_count: 0,
        status: 'approved',
        hero_image_path: null,
        images: [],
      })
      return
    }
    apiAuth(`/admin/bases/${baseId}`).then(setForm).catch((e) => toast.error(e.message))
  }, [baseId, isNew, toast])

  if (!form) return <div className="empty-state">Loading…</div>

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const onChangeNum = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.value === '' ? null : Number(e.target.value) }))

  const save = async (e) => {
    e.preventDefault()
    const tagsArr = Array.isArray(form.tags)
      ? form.tags
      : String(form.tags || '')
          .split(/[\s,]+/)
          .filter(Boolean)
    const payload = {
      title: form.title,
      builder_name: form.builder_name,
      builder_affiliation: form.builder_affiliation,
      description: form.description,
      builder_notes: form.builder_notes,
      platform: form.platform || null,
      galaxy: form.galaxy || null,
      region: form.region || null,
      portal_address: form.portal_address || null,
      tags: tagsArr,
      star_count: form.star_count,
      view_count: form.view_count,
      status: form.status,
    }
    try {
      const res = isNew
        ? await apiAuth('/admin/bases', { method: 'POST', body: payload })
        : await apiAuth(`/admin/bases/${baseId}`, { method: 'PUT', body: payload })
      toast.success(`Saved ${res.id}.`)
      onSaved?.(res)
    } catch (err) {
      toast.error(`Save failed: ${err.message}`)
    }
  }

  const uploadHero = async (e) => {
    const file = e.target.files?.[0]
    if (!file || isNew) {
      if (isNew) toast.error('Save the base first, then add images.')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await fetch(`/api/admin/bases/${baseId}/hero-image`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setForm((f) => ({ ...f, hero_image_path: data.hero_image_path }))
      toast.success('Hero image uploaded.')
    } catch (err) {
      toast.error(`Upload failed: ${err.message}`)
    }
  }

  const uploadGallery = async (e) => {
    const file = e.target.files?.[0]
    if (!file || isNew) {
      if (isNew) toast.error('Save the base first, then add images.')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await fetch(`/api/admin/bases/${baseId}/gallery`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setForm((f) => ({ ...f, images: [...(f.images || []), data] }))
      toast.success('Gallery image added.')
    } catch (err) {
      toast.error(`Upload failed: ${err.message}`)
    }
  }

  const deleteGallery = async (imgId) => {
    if (!confirm('Delete this image?')) return
    try {
      await apiAuth(`/admin/bases/${baseId}/gallery/${imgId}`, { method: 'DELETE' })
      setForm((f) => ({ ...f, images: (f.images || []).filter((x) => x.id !== imgId) }))
      toast.success('Image deleted.')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const tagsAsString = Array.isArray(form.tags) ? form.tags.join(' ') : form.tags || ''

  return (
    <form onSubmit={save}>
      <div className="form-grid">
        <div className="form-field span-2">
          <label>Title *</label>
          <input required value={form.title} onChange={onChange('title')} />
        </div>
        <div className="form-field">
          <label>Builder name *</label>
          <input required value={form.builder_name} onChange={onChange('builder_name')} />
        </div>
        <div className="form-field">
          <label>Affiliation</label>
          <input value={form.builder_affiliation || ''} onChange={onChange('builder_affiliation')} />
        </div>
        <div className="form-field">
          <label>Platform</label>
          <select value={form.platform || ''} onChange={onChange('platform')}>
            <option value="">—</option>
            {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
          </select>
        </div>
        <div className="form-field">
          <label>Status</label>
          <select value={form.status || 'pending'} onChange={onChange('status')}>
            {STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
          </select>
        </div>
        <div className="form-field">
          <label>Galaxy</label>
          <input value={form.galaxy || ''} onChange={onChange('galaxy')} />
        </div>
        <div className="form-field">
          <label>Region</label>
          <input value={form.region || ''} onChange={onChange('region')} />
        </div>
        <div className="form-field">
          <label>Portal address</label>
          <input value={form.portal_address || ''} onChange={onChange('portal_address')} />
        </div>
        <div className="form-field span-2">
          <label>Tags (space-separated)</label>
          <input
            value={tagsAsString}
            onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value.split(/\s+/).filter(Boolean) }))}
          />
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description || ''} onChange={onChange('description')} />
        </div>
        <div className="form-field span-2">
          <label>Builder's notes</label>
          <textarea value={form.builder_notes || ''} onChange={onChange('builder_notes')} />
        </div>
        <div className="form-field">
          <label>Stars</label>
          <input type="number" value={form.star_count ?? 0} onChange={onChangeNum('star_count')} />
        </div>
        <div className="form-field">
          <label>Views</label>
          <input type="number" value={form.view_count ?? 0} onChange={onChangeNum('view_count')} />
        </div>

        {!isNew && (
          <>
            <div className="form-field span-2">
              <label>Hero image</label>
              <div className="upload-row">
                {form.hero_image_path ? (
                  <img src={form.hero_image_path} alt="hero" />
                ) : (
                  <span className="muted" style={{ color: 'var(--text-tertiary)' }}>none</span>
                )}
                <input type="file" accept="image/*" onChange={uploadHero} />
              </div>
            </div>
            <div className="form-field span-2">
              <label>Gallery</label>
              <input type="file" accept="image/*" onChange={uploadGallery} />
              <div className="gallery-admin" style={{ marginTop: '0.5rem' }}>
                {(form.images || []).map((img) => (
                  <div key={img.id} className="gal-item">
                    <img src={img.image_path} alt={img.caption || ''} />
                    <button type="button" className="del" onClick={() => deleteGallery(img.id)}>×</button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn primary">{isNew ? 'Create base' : 'Save changes'}</button>
      </div>
    </form>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Modal from '../components/Modal'
import { useToast } from '../context/ToastContext'
import { useIdentity } from '../context/IdentityContext'
import { PLATFORMS as IDENTITY_PLATFORMS } from '../identity/identityStorage'

const PLATFORMS = [
  { value: 'all', label: 'All' },
  { value: 'pc', label: 'PC' },
  { value: 'ps', label: 'PlayStation' },
  { value: 'xbox', label: 'Xbox' },
  { value: 'switch', label: 'Switch' },
]

const PLATFORM_LABEL = { pc: 'PC', ps: 'PS5', xbox: 'Xbox', switch: 'Switch' }

// How many gallery photos a submitter can attach (mirrors the backend cap).
const MAX_GALLERY = 4

function BaseCard({ base }) {
  const heroBg = base.hero_image_path
    ? { backgroundImage: `url(${base.hero_image_path})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : null
  return (
    <Link to={`/civs/bases/${base.id}`} className="base-card" style={{ textDecoration: 'none', color: 'inherit' }}>
      <div className="base-hero" style={heroBg || undefined}>
        <div className="base-tags">
          {base.platform && (
            <span className={`base-tag platform-${base.platform}`}>
              {PLATFORM_LABEL[base.platform] || base.platform}
            </span>
          )}
        </div>
        {!base.hero_image_path && (
          <div className={`placeholder-media ${base.hero_color || 'cyan'}`}>[ Hero shot · 16:10 ]</div>
        )}
      </div>
      <div className="base-info">
        <h3 className="base-title">{base.title}</h3>
        <div className="base-builder">
          by <strong>{base.builder_name}</strong>
          {base.builder_affiliation ? ` · ${base.builder_affiliation}` : ''}
        </div>
        <p className="base-blurb">{base.blurb || base.description?.slice(0, 200)}</p>
        <div className="base-meta">
          {base.galaxy && <span>◇ {base.galaxy}</span>}
          {base.region && <span>◐ {base.region}</span>}
          <span>{base.stars_display}</span>
        </div>
      </div>
    </Link>
  )
}

function CommunityCard({ c }) {
  return (
    <article className="civ-card">
      <div className="civ-head">
        {c.logo_image_path ? (
          <img className="civ-logo" src={c.logo_image_path} alt={`${c.name} logo`} />
        ) : (
          <div className="civ-logo civ-logo-empty">{(c.name || '?').charAt(0).toUpperCase()}</div>
        )}
        <div className="civ-head-text">
          <div className="civ-name">{c.name}</div>
          {c.language && <div className="civ-language">{c.language}</div>}
        </div>
      </div>
      {c.description && <p className="civ-desc">{c.description}</p>}
      {c.link_url ? (
        <a className="civ-link" href={c.link_url} target="_blank" rel="noreferrer">Visit →</a>
      ) : (
        <a className="civ-link">—</a>
      )}
    </article>
  )
}

// Map identity's platform index → backend's platform string.
// Identity uses: ["Steam", "GOG", "Xbox", "Switch", "PlayStation"]
// Backend expects: pc | xbox | switch | ps
function platformFromIdentity(identityPlatform) {
  if (typeof identityPlatform !== 'number') return null
  const label = IDENTITY_PLATFORMS[identityPlatform]
  if (!label) return null
  if (label === 'Steam' || label === 'GOG') return 'pc'
  if (label === 'Xbox') return 'xbox'
  if (label === 'Switch') return 'switch'
  if (label === 'PlayStation') return 'ps'
  return null
}

// Thumbnail strip / preview for locally-selected files (revokes object URLs on change).
function useObjectUrls(files) {
  const urls = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls])
  return urls
}

function SubmitBaseForm({ onSubmitted, onClose }) {
  const { identity } = useIdentity()
  const prefillPlatform = platformFromIdentity(identity?.platform)
  const [form, setForm] = useState(() => ({
    title: '',
    builder_name: identity?.name || '',
    builder_affiliation: identity?.affiliation || '',
    description: '',
    builder_notes: '',
    platform: prefillPlatform || 'pc',
    galaxy: '',
    region: '',
    portal_address: '',
    submitter_email: '',
    submitter_discord_id: '',
  }))
  const [heroFile, setHeroFile] = useState(null)
  const [galleryFiles, setGalleryFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState('') // '', 'submitting', 'uploading'
  const toast = useToast()

  const heroUrls = useObjectUrls(heroFile ? [heroFile] : [])
  const galleryUrls = useObjectUrls(galleryFiles)

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onPickGallery = (e) => {
    const picked = Array.from(e.target.files || [])
    setGalleryFiles(picked.slice(0, MAX_GALLERY))
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setPhase('submitting')
    try {
      const res = await api('/submissions/bases', { method: 'POST', body: { ...form } })
      const id = res.id

      // Photos attach to the just-created (still-pending) base. Best-effort:
      // the base is already queued, so a photo hiccup shouldn't lose the whole
      // submission — we just warn about the photo.
      let photoWarn = null
      const files = [
        ...(heroFile ? [{ f: heroFile, path: `/submissions/bases/${id}/hero` }] : []),
        ...galleryFiles.slice(0, MAX_GALLERY).map((f) => ({ f, path: `/submissions/bases/${id}/gallery` })),
      ]
      if (files.length) {
        setPhase('uploading')
        for (const { f, path } of files) {
          try {
            const fd = new FormData()
            fd.append('file', f)
            await api(path, { method: 'POST', body: fd })
          } catch (imgErr) {
            photoWarn = imgErr.message
          }
        }
      }

      if (photoWarn) {
        toast.error(`Base submitted as ${id}, but a photo didn't upload: ${photoWarn}`)
      } else {
        toast.success(`Submitted! Pending moderation as ${id}.`)
      }
      onSubmitted?.(res)
      onClose()
    } catch (err) {
      toast.error(`Submission failed: ${err.message}`)
    } finally {
      setBusy(false)
      setPhase('')
    }
  }

  const submitLabel = busy
    ? (phase === 'uploading' ? 'Uploading photos…' : 'Submitting…')
    : 'Submit base'

  return (
    <form onSubmit={submit}>
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
          <input value={form.builder_affiliation} onChange={onChange('builder_affiliation')} placeholder="Voyager's Haven" />
        </div>

        {/* --- Photos --- */}
        <div className="form-field span-2">
          <label>Cover photo <span className="field-hint">· optional, but bases with a photo stand out</span></label>
          <input type="file" accept="image/*" onChange={(e) => setHeroFile(e.target.files?.[0] || null)} />
          {heroUrls[0] && (
            <div className="submit-photo-preview">
              <img src={heroUrls[0]} alt="cover preview" />
            </div>
          )}
        </div>
        <div className="form-field span-2">
          <label>More photos <span className="field-hint">· up to {MAX_GALLERY}</span></label>
          <input type="file" accept="image/*" multiple onChange={onPickGallery} />
          {galleryUrls.length > 0 && (
            <div className="submit-photo-strip">
              {galleryUrls.map((u, i) => (
                <img key={i} src={u} alt={`photo ${i + 1}`} />
              ))}
            </div>
          )}
        </div>

        <div className="form-field">
          <label>Platform</label>
          <select value={form.platform} onChange={onChange('platform')}>
            <option value="pc">PC</option>
            <option value="ps">PlayStation</option>
            <option value="xbox">Xbox</option>
            <option value="switch">Switch</option>
          </select>
        </div>
        <div className="form-field">
          <label>Galaxy</label>
          <input value={form.galaxy} onChange={onChange('galaxy')} placeholder="Euclid" />
        </div>
        <div className="form-field">
          <label>Region</label>
          <input value={form.region} onChange={onChange('region')} />
        </div>
        <div className="form-field">
          <label>Portal address</label>
          <input value={form.portal_address} onChange={onChange('portal_address')} placeholder="10A8 · F8AC · 1023 · 0001" />
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description} onChange={onChange('description')} />
        </div>
        <div className="form-field span-2">
          <label>Builder's notes</label>
          <textarea value={form.builder_notes} onChange={onChange('builder_notes')} />
        </div>
        <div className="form-field">
          <label>Your email (for follow-up)</label>
          <input value={form.submitter_email} onChange={onChange('submitter_email')} type="email" />
        </div>
        <div className="form-field">
          <label>Your Discord ID</label>
          <input value={form.submitter_discord_id} onChange={onChange('submitter_discord_id')} />
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="submit" className="btn primary" disabled={busy}>{submitLabel}</button>
      </div>
    </form>
  )
}

function SubmitCommunityForm({ onSubmitted, onClose }) {
  const [form, setForm] = useState({ name: '', language: '', description: '', link_url: '' })
  const [logoFile, setLogoFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState('')
  const toast = useToast()
  const logoUrls = useObjectUrls(logoFile ? [logoFile] : [])
  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setPhase('submitting')
    try {
      const res = await api('/submissions/communities', { method: 'POST', body: form })
      let logoWarn = null
      if (logoFile) {
        setPhase('uploading')
        try {
          const fd = new FormData()
          fd.append('file', logoFile)
          await api(`/submissions/communities/${res.id}/logo`, { method: 'POST', body: fd })
        } catch (imgErr) {
          logoWarn = imgErr.message
        }
      }
      if (logoWarn) toast.error(`Community submitted as ${res.id}, but the logo didn't upload: ${logoWarn}`)
      else toast.success(`Submitted! Pending moderation as ${res.id}.`)
      onSubmitted?.(res)
      onClose()
    } catch (err) {
      toast.error(`Submission failed: ${err.message}`)
    } finally {
      setBusy(false)
      setPhase('')
    }
  }
  const submitLabel = busy ? (phase === 'uploading' ? 'Uploading logo…' : 'Submitting…') : 'Submit community'
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <div className="form-field span-2">
          <label>Community name *</label>
          <input required value={form.name} onChange={onChange('name')} />
        </div>
        <div className="form-field">
          <label>Language</label>
          <input value={form.language} onChange={onChange('language')} placeholder="English" />
        </div>
        <div className="form-field">
          <label>Link</label>
          <input value={form.link_url} onChange={onChange('link_url')} placeholder="https://" />
        </div>
        <div className="form-field span-2">
          <label>Logo <span className="field-hint">· optional, square works best</span></label>
          <input type="file" accept="image/*" onChange={(e) => setLogoFile(e.target.files?.[0] || null)} />
          {logoUrls[0] && (
            <div className="submit-logo-preview">
              <img src={logoUrls[0]} alt="logo preview" />
            </div>
          )}
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description} onChange={onChange('description')} />
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="submit" className="btn primary" disabled={busy}>{submitLabel}</button>
      </div>
    </form>
  )
}

export default function CivsAndBases() {
  const [tab, setTab] = useState('communities')
  const [bases, setBases] = useState([])
  const [communities, setCommunities] = useState([])
  const [platform, setPlatform] = useState('all')
  const [openModal, setOpenModal] = useState(null) // 'base' | 'community' | null

  const load = () => {
    api('/bases').then(setBases).catch(() => setBases([]))
    api('/communities').then(setCommunities).catch(() => setCommunities([]))
  }
  useEffect(load, [])

  const filtered = useMemo(() => {
    return bases.filter((b) => {
      if (platform !== 'all' && b.platform !== platform) return false
      return true
    })
  }, [bases, platform])

  return (
    <div className="container">
      <div className="page-header">
        <div className="page-eyebrow">// The Showcase</div>
        <h1 className="page-title">Civilizations &amp; Bases</h1>
        <div className="page-meta">Communities and creations from across the multiverse</div>
      </div>

      <div className="section-tabs">
        <button className={`section-tab${tab === 'communities' ? ' active' : ''}`} onClick={() => setTab('communities')}>Communities</button>
        <button className={`section-tab${tab === 'bases' ? ' active' : ''}`} onClick={() => setTab('bases')}>Bases</button>
      </div>

      {tab === 'communities' && (
        <div className="section-pane active">
          <div className="inline-form-toggle">
            <button className="btn primary" onClick={() => setOpenModal('community')}>+ Submit a community</button>
          </div>
          <div className="civ-grid">
            {communities.length === 0 ? (
              <div className="empty-state">No communities approved yet.</div>
            ) : (
              communities.map((c) => <CommunityCard key={c.id} c={c} />)
            )}
          </div>
        </div>
      )}

      {tab === 'bases' && (
        <div className="section-pane active">
          <div className="filter-section">
            <div className="filter-section-label">Platform</div>
            <div className="filter-bar" data-filter-group="platform">
              {PLATFORMS.map((p) => (
                <button
                  key={p.value}
                  className={`filter-chip${platform === p.value ? ' active' : ''}`}
                  onClick={() => setPlatform(p.value)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="inline-form-toggle">
            <button className="btn primary" onClick={() => setOpenModal('base')}>+ Submit a base</button>
          </div>

          <div className="base-grid">
            {filtered.length === 0 ? (
              bases.length === 0 ? (
                <div className="empty-state">
                  No bases yet — be the first to submit one. Every build gets reviewed before it appears here.
                </div>
              ) : (
                <div className="no-results show">No bases on this platform. Try “All”.</div>
              )
            ) : (
              filtered.map((b) => <BaseCard key={b.id} base={b} />)
            )}
          </div>
        </div>
      )}

      <Modal open={openModal === 'base'} title="Submit a base" onClose={() => setOpenModal(null)} wide>
        <SubmitBaseForm onSubmitted={load} onClose={() => setOpenModal(null)} />
      </Modal>
      <Modal open={openModal === 'community'} title="Submit a community" onClose={() => setOpenModal(null)}>
        <SubmitCommunityForm onSubmitted={load} onClose={() => setOpenModal(null)} />
      </Modal>
    </div>
  )
}

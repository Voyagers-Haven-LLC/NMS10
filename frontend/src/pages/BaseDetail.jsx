import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'

const PLATFORM_LABEL = { pc: 'PC', ps: 'PS5', xbox: 'Xbox', switch: 'Switch' }
const HERO_PALETTE = ['cyan', 'gold', 'purple', 'dark']

function pickHeroColor(id, fallback) {
  if (fallback) return fallback
  const h = (id || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return HERO_PALETTE[h % HERO_PALETTE.length]
}

export default function BaseDetail() {
  const { id } = useParams()
  const [base, setBase] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setBase(null)
    setError(null)
    api(`/bases/${id}`)
      .then(setBase)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <div className="container">
        <div className="page-header">
          <Link to="/civs" className="back-link">← Back to bases</Link>
          <h1 className="page-title">Not found</h1>
          <div className="page-meta">{error}</div>
        </div>
      </div>
    )
  }
  if (!base) {
    return (
      <div className="container">
        <div className="page-header">
          <Link to="/civs" className="back-link">← Back to bases</Link>
          <div className="page-meta">Loading…</div>
        </div>
      </div>
    )
  }

  const heroColor = pickHeroColor(base.id, base.hero_color)
  const heroBg = base.hero_image_path
    ? { backgroundImage: `url(${base.hero_image_path})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : null

  return (
    <div className="container">
      <div className="page-header">
        <Link to="/civs" className="back-link">← Back to bases</Link>
        <h1 className="page-title">{base.title}</h1>
        <div className="page-meta">
          {(PLATFORM_LABEL[base.platform] || base.platform || '?')} · {base.galaxy || '—'} · {base.class || '—'}
        </div>
      </div>

      <div className="detail-hero" style={heroBg || undefined}>
        {!base.hero_image_path && (
          <div className={`placeholder-media ${heroColor}`}>[ Hero shot · 21:9 ]</div>
        )}
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <div className="detail-builder-block">
            <div className="detail-builder-avatar">{base.builder_initials || '??'}</div>
            <div>
              <div className="detail-builder-name">{base.builder_name}</div>
              {base.builder_affiliation && (
                <div className="detail-builder-affiliation">{base.builder_affiliation}</div>
              )}
            </div>
          </div>

          <h2>About this build</h2>
          <p>{base.description || '—'}</p>

          {base.images?.length > 0 && (
            <>
              <h2>Gallery</h2>
              <div className="gallery">
                {base.images.map((img, i) => (
                  <div key={i} className="gallery-thumb">
                    <img src={img.image_path} alt={img.caption || ''} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                ))}
              </div>
            </>
          )}

          {base.builder_notes && (
            <>
              <h2>Builder's Notes</h2>
              <p>{base.builder_notes}</p>
            </>
          )}
        </div>

        <aside className="detail-side">
          <div className="info-card">
            <h3>Location</h3>
            <div className="info-row"><span className="key">Galaxy</span><span className="val">{base.galaxy || '—'}</span></div>
            <div className="info-row"><span className="key">Region</span><span className="val">{base.region || '—'}</span></div>
            <div className="info-row"><span className="key">Class</span><span className="val">{base.class || '—'}</span></div>
            <div className="info-row"><span className="key">Platform</span><span className="val">{PLATFORM_LABEL[base.platform] || base.platform || '—'}</span></div>
          </div>
          {base.portal_address && (
            <div className="info-card">
              <h3>Portal Address</h3>
              <div className="portal-address">{base.portal_address}</div>
            </div>
          )}
          <div className="info-card">
            <h3>Stats</h3>
            <div className="info-row"><span className="key">Submitted</span><span className="val">{base.submitted_display || '—'}</span></div>
            <div className="info-row"><span className="key">Stars</span><span className="val">{base.stars_display}</span></div>
            <div className="info-row"><span className="key">Visits</span><span className="val">{base.visits_display}</span></div>
          </div>
        </aside>
      </div>
    </div>
  )
}

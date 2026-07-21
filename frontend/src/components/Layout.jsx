import { NavLink, Link, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useCountdown, pad } from './useCountdown'
import { useIdentity } from '../context/IdentityContext'
import IdentityModal from './IdentityModal'

const NAV_ITEMS = [
  { to: '/', label: 'Expedition' },
  { to: '/civs', label: 'Civs & Bases' },
  { to: '/meetups', label: 'Meetups' },
  { to: '/socials', label: 'Socials' },
  { to: '/faq', label: 'FAQ' },
]

function MiniCountdown() {
  // Visibility is controlled entirely by the .header-countdown class,
  // which v9 hides at <=768px. Don't override with inline display.
  const c = useCountdown()
  return (
    <div className="header-countdown">
      <span className="num">{c.reached ? '0' : c.days}</span>D
      <span className="num">{c.reached ? '00' : pad(c.hours)}</span>H
      <span className="num">{c.reached ? '00' : pad(c.minutes)}</span>M
    </div>
  )
}

function SteamBadge() {
  const [count, setCount] = useState(null)
  useEffect(() => {
    let alive = true
    const fetchCount = () =>
      api('/steam-count')
        .then((d) => alive && setCount(d.player_count))
        .catch(() => {})
    fetchCount()
    const id = setInterval(fetchCount, 30000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])
  if (count == null) return null
  return (
    <div className="steam-count" title="Live Steam concurrent players">
      <strong>{count.toLocaleString()}</strong> in-game
    </div>
  )
}

function IdentityBadge({ onOpen }) {
  // Shows in the header. Two states: empty (subdued cyan invitation) and
  // filled (gold-tinted name pill). Click opens the modal in either state.
  const { identity } = useIdentity()
  if (!identity) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="identity-badge identity-badge-empty"
        aria-label="Set your Traveler identity"
      >
        <span className="identity-icon">◇</span>
        <span className="identity-label">Set your Traveler identity</span>
      </button>
    )
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      className="identity-badge identity-badge-set"
      aria-label={`Edit identity (currently ${identity.name})`}
    >
      <span className="identity-icon">👤</span>
      <span className="identity-label">{identity.name}</span>
      <span className="identity-caret">▾</span>
    </button>
  )
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <span>© 2026 Voyager's Haven · Built for the NMS10 collaborative</span>
        <span>Banner &amp; logo: Nerozii &amp; Mr Sinister</span>
      </div>
    </footer>
  )
}

export default function Layout({ children }) {
  const { pathname } = useLocation()
  const isExpedition = pathname === '/'
  const isBaseDetail = pathname.startsWith('/civs/bases/')
  const isAdmin = pathname.startsWith('/admin')

  const [identityOpen, setIdentityOpen] = useState(false)

  // Mini countdown shows on every page except expedition (matches v9 logic).
  const showMini = !isExpedition && !isBaseDetail
  // Nav highlight: base detail counts as civs (matches v9 logic).
  const navCurrent = isBaseDetail ? '/civs' : pathname

  return (
    <>
      <header className="site-header">
        <nav className="nav">
          <Link to="/" className="brand" style={{ textDecoration: 'none', color: 'inherit' }}>
            <img
              src="/nms10-logo.png"
              alt=""
              className="brand-mark"
              style={{
                width: 32,
                height: 32,
                objectFit: 'contain',
                background: 'transparent',
                boxShadow: 'none',
              }}
            />
            <span>NMS / 10</span>
          </Link>

          {showMini ? <MiniCountdown /> : <span className="header-spacer" />}

          <div className="nav-right">
            <SteamBadge />
            <IdentityBadge onOpen={() => setIdentityOpen(true)} />
            <ul className="nav-links">
              {NAV_ITEMS.map((item) => (
                <li
                  key={item.to}
                  className={navCurrent === item.to ? 'current' : ''}
                  style={{ listStyle: 'none' }}
                >
                  <NavLink
                    to={item.to}
                    style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
              {isAdmin && (
                <li className="current" style={{ listStyle: 'none' }}>
                  <Link to="/admin" style={{ textDecoration: 'none', color: 'inherit' }}>
                    Admin
                  </Link>
                </li>
              )}
            </ul>
          </div>
        </nav>
      </header>
      <main>{children}</main>
      <Footer />
      <IdentityModal open={identityOpen} onClose={() => setIdentityOpen(false)} />
    </>
  )
}

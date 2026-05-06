import { useEffect, useState } from 'react'

// Bump this if the banner art changes — visitors who already saw v1 will then
// see the new splash once.
const SEEN_KEY = 'nms10_splash_seen_v1'
const AUTO_DISMISS_MS = 3000
const FADE_MS = 400

export default function Splash() {
  const [phase, setPhase] = useState(null)
  // phase states:
  //   null     — undecided (still reading localStorage)
  //   'shown'  — fully visible
  //   'fading' — opacity transitioning to 0
  //   'done'   — unmounted from the tree

  useEffect(() => {
    let seen = false
    try {
      seen = localStorage.getItem(SEEN_KEY) === '1'
    } catch {}
    setPhase(seen ? 'done' : 'shown')
  }, [])

  useEffect(() => {
    if (phase !== 'shown') return
    const t = setTimeout(() => setPhase('fading'), AUTO_DISMISS_MS)
    return () => clearTimeout(t)
  }, [phase])

  useEffect(() => {
    if (phase !== 'fading') return
    try {
      localStorage.setItem(SEEN_KEY, '1')
    } catch {}
    const t = setTimeout(() => setPhase('done'), FADE_MS)
    return () => clearTimeout(t)
  }, [phase])

  if (phase === null || phase === 'done') return null

  return (
    <div
      className={`splash${phase === 'fading' ? ' splash-fading' : ''}`}
      onClick={() => setPhase('fading')}
      role="button"
      aria-label="Dismiss intro"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') && setPhase('fading')}
    >
      <div className="splash-inner">
        <img
          src="/nms10-banner.jpg"
          alt="Celebrating 10 Years of No Man's Sky · #NMS10"
          className="splash-banner"
          decoding="async"
          fetchPriority="high"
        />
        <div className="splash-hint">click anywhere to enter</div>
      </div>
    </div>
  )
}

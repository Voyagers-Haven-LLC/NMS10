import { useEffect, useState } from 'react'
import { useCountdown, pad } from '../components/useCountdown'
import { useIdentity } from '../context/IdentityContext'
import IdentityModal from '../components/IdentityModal'

// NMS10 brand defaults for the DreamingFox card generator.
//   cc=10  → corner color #851717 (deep red, matches the hex 10 logo)
//   mc=19  → main color #000000 (black, the badge background)
//   s=26   → sigil index DreamingFox confirmed for the NMS10 card
// If you want a different default palette, change here only — the rest
// of the URL is identity-driven.
// TODO: revisit cc/mc once Mr Sinister + DreamingFox confirm a final
// canonical color combo for the anniversary card. Today's pick is the
// closest to the official banner palette in DreamingFox's existing options.
const CARD_BRAND_PARAMS = { cc: '10', mc: '19', s: '26' }

function buildCardUrl(identity) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(CARD_BRAND_PARAMS)) params.set(k, v)
  if (identity) {
    if (identity.name) params.set('n', identity.name)
    params.set('r', String(identity.race))
    if (identity.affiliation) params.set('a', identity.affiliation)
    params.set('p', String(identity.platform))
  }
  return `https://grs.dreamingfox.dev/card?${params.toString()}`
}

const MILESTONES = [
  {
    id: '1',
    title: 'Answer the Call',
    desc: 'Be in-game on August 9, 2026 at 18:00 UTC. The main synchronized moment of the anniversary celebration.',
  },
  {
    id: '2',
    title: 'Echoes Across the Stars',
    desc: 'Use #NMS10 and help spread the message. Send the signal further across communities and platforms.',
  },
  {
    id: '3',
    title: 'Honour the Symbol',
    desc: 'Discover, build, use, or share the anniversary logo. Every expedition needs a symbol.',
  },
  {
    id: '4',
    title: 'A Universe Remembered',
    desc: "Share something inspired by your No Man's Sky journey. Your story is part of the universe.",
  },
  {
    id: '5',
    title: 'Rendezvous with Travellers',
    desc: 'Take part in a community event, challenge, or gathering. Find other Travellers along the way.',
  },
  {
    id: '6',
    title: 'Constellations of Community',
    desc: "Help showcase a No Man's Sky community. The universe is wider when Travellers find each other.",
  },
  {
    id: '7',
    title: 'A Tribute Among the Stars',
    desc: 'Create or share a tribute for the anniversary, in-game or beyond. Leave a positive mark on the universe.',
  },
  {
    id: '8',
    title: 'Voices of the Dreamers',
    desc: 'Watch, join, or support anniversary content. Tune in to the celebration. Every voice helps the signal travel further.',
  },
]

const STORAGE_KEY = 'nms10_milestones'

function loadCompleted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw))
  } catch {
    return new Set()
  }
}
function saveCompleted(set) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]))
  } catch {}
}

function MilestoneCard({ m, completed, onToggle }) {
  return (
    <article
      className={`milestone-card${completed ? ' completed' : ''}`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onToggle()}
    >
      <div className="milestone-header">
        <div>
          <div className="milestone-number">// Milestone {pad(parseInt(m.id, 10))}</div>
        </div>
        <div className="milestone-checkbox" />
      </div>
      <div className="milestone-icon">{pad(parseInt(m.id, 10))}</div>
      <h3 className="milestone-title">{m.title}</h3>
      <p className="milestone-desc">{m.desc}</p>
      <div className="milestone-status">{completed ? 'Completed' : 'Status'}</div>
    </article>
  )
}

export default function Expedition() {
  const c = useCountdown()
  const [completed, setCompleted] = useState(() => loadCompleted())

  const toggle = (id) => {
    setCompleted((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      saveCompleted(next)
      return next
    })
  }

  const count = completed.size
  const reward = count >= 8

  return (
    <section data-view="expedition" style={{ display: 'block' }}>
      <div className="expedition-hero">
        <div className="expedition-eyebrow">// 10 Years Expedition</div>
        <h1 className="expedition-title">
          Expedition for the <span className="accent">Dreamers</span>
        </h1>
        <p className="expedition-tagline">While others sleep, we're still dreaming. Are you?</p>
      </div>

      <div className={`big-countdown${c.reached ? ' anniversary-mode' : ''}`}>
        <div className="countdown-grid">
          <div className="countdown-cell">
            <div className="countdown-number">{pad(c.days, 3)}</div>
            <div className="countdown-label">Days</div>
          </div>
          <div className="countdown-cell">
            <div className="countdown-number">{pad(c.hours)}</div>
            <div className="countdown-label">Hours</div>
          </div>
          <div className="countdown-cell">
            <div className="countdown-number">{pad(c.minutes)}</div>
            <div className="countdown-label">Minutes</div>
          </div>
          <div className="countdown-cell">
            <div className="countdown-number">{pad(c.seconds)}</div>
            <div className="countdown-label">Seconds</div>
          </div>
        </div>
        <div className="countdown-target">
          August 9, 2026 · 18:00 UTC · The synchronized in-game gathering
        </div>

        <div className="anniversary-banner">
          <div className="marker">10 / 10</div>
          <div className="text">
            A decade of discovery. Thank you for travelling with us, Travelers. The journey is far from over.
          </div>
        </div>
      </div>

      <div className="progress-strip">
        <div className="progress-text">
          <span className="num">{count}</span> / 8 Milestones
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${(count / 8) * 100}%` }} />
        </div>
      </div>

      <div className="milestone-section">
        <h2 className="milestone-section-title">The Journey</h2>
        <div className="milestone-section-meta">
          Complete at your own pace · Honor system · Click any card to mark it
        </div>

        <div className="milestone-grid">
          {MILESTONES.map((m) => (
            <MilestoneCard
              key={m.id}
              m={m}
              completed={completed.has(m.id)}
              onToggle={() => toggle(m.id)}
            />
          ))}
        </div>
      </div>

      <RewardSection reward={reward} />
    </section>
  )
}

function RewardSection({ reward }) {
  const { identity } = useIdentity()
  const [identityOpen, setIdentityOpen] = useState(false)

  let cta
  if (!reward) {
    // Locked — same as before, click does nothing
    cta = (
      <a href="#" className="reward-cta" onClick={(e) => e.preventDefault()}>
        Claim your card →
      </a>
    )
  } else if (!identity) {
    // 8/8 done but no identity — clicking opens the modal so they can
    // personalize before claiming. After they save, this re-renders with
    // their identity and the link goes live.
    cta = (
      <a
        href="#"
        className="reward-cta"
        onClick={(e) => {
          e.preventDefault()
          setIdentityOpen(true)
        }}
      >
        Set your identity to claim →
      </a>
    )
  } else {
    cta = (
      <a
        href={buildCardUrl(identity)}
        target="_blank"
        rel="noreferrer"
        className="reward-cta"
      >
        Claim your card →
      </a>
    )
  }

  return (
    <div className="reward-section">
      <div className={`reward-card${reward ? ' unlocked' : ''}`}>
        <div className="reward-eyebrow">// The Reward</div>
        <div className="reward-icon">★</div>
        <h2 className="reward-title">Dreaming Traveller Card</h2>
        <p className="reward-desc">
          Complete all eight milestones to claim your symbolic badge of participation in the 10th anniversary expedition. Generator by DreamingFox.
        </p>
        {cta}
      </div>
      <IdentityModal open={identityOpen} onClose={() => setIdentityOpen(false)} />
    </div>
  )
}

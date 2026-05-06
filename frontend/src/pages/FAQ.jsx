import { useState } from 'react'

const FAQ_ITEMS = [
  {
    q: "What is the No Man's Sky 10th Anniversary celebration?",
    a: "On August 9, 2026, No Man's Sky turns 10 years old. To celebrate, the community is organizing a global in-game gathering to thank Hello Games for ten incredible years. The goal is simple: bring as many Travelers as possible together in-game during the same time window and make this moment historic.",
  },
  {
    q: 'When should players be in-game?',
    a: (
      <>
        The main synchronized moment is planned for <strong>August 9, 2026 — 18:00 UTC</strong>.
        <br /><br />
        Equivalent times: 20:00 CEST · 19:00 BST · 2:00 PM EDT · 11:00 AM PDT.
        <br /><br />
        Players from all platforms are invited to connect during this time window.
      </>
    ),
  },
  {
    q: 'What is the main goal?',
    a: 'Create a massive worldwide player connection across all platforms, with the goal of beating the 2016 launch player peak. The event is open to all platforms.',
  },
  {
    q: 'How can I participate?',
    a: 'Most importantly: be in-game on August 9, 2026 at 18:00 UTC. Beyond that — use #NMS10, share the event with your community, complete the Expedition for the Dreamers milestones, join community events or challenges, create or share anniversary content, and support streams, videos, base tours, and community projects.',
  },
  {
    q: 'What is the 10 Years Expedition?',
    a: 'A symbolic community journey for players who want to take part in the anniversary. You complete a series of milestones — be in-game for the global gathering, share the event, create or share something inspired by your journey, discover community projects, support streams or videos, and celebrate with other Travelers. There is no pressure, no competition, and no official requirement. Take part your way.',
  },
  {
    q: 'What is the Dreaming Traveller Card?',
    a: 'A symbolic badge of participation in the 10 Years Expedition. It is not an official reward, a competition, or a requirement — it is a personal memory of your place in the celebration. Complete all 8 milestones to claim yours.',
  },
  {
    q: 'What is the anniversary logo?',
    a: "A community-made emblem created for the 10th anniversary. The final version, along with the idea of building it using in-game elements, comes from Mr Sinister and Dashboard Devil. It brings together the 10th anniversary, Hello Games' Atlas, and the players' Universal Heartbeat into one shared symbol. Yes — it can be recreated in-game using existing visual elements.",
  },
  {
    q: 'Is this affiliated with Hello Games?',
    a: 'No. This is a community celebration. Not affiliated with Hello Games.',
  },
]

const DOWNLOADS = [
  { name: 'Anniversary Logo', desc: 'PNG · SVG · Transparent' },
  { name: 'Banners & Templates', desc: 'For Discord, social, profile use' },
  { name: 'In-Game Logo Tutorial', desc: 'By Dashboard Devil (English)' },
  { name: 'In-Game Logo Tutorial', desc: 'By la Checktitude (FR + EN subs)' },
  { name: 'Anniversary Music Playlist', desc: 'Community AI music tribute' },
  { name: 'DreamingFox Card Generator', desc: 'Make your own Traveler card' },
]

export default function FAQ() {
  const [openIdx, setOpenIdx] = useState(null)
  return (
    <div className="container">
      <div className="page-header">
        <div className="page-eyebrow">// Questions</div>
        <h1 className="page-title">Frequently Asked</h1>
        <div className="page-meta">Everything you need to know about the anniversary celebration</div>
      </div>

      <div className="faq-wrap">
        {FAQ_ITEMS.map((item, i) => {
          const open = openIdx === i
          return (
            <div key={i} className={`faq-item${open ? ' open' : ''}`}>
              <button className="faq-question" onClick={() => setOpenIdx(open ? null : i)}>
                <span>{item.q}</span>
                <span className="faq-icon">+</span>
              </button>
              <div className="faq-answer">{item.a}</div>
            </div>
          )
        })}
      </div>

      <div className="downloads-section">
        <h2 className="downloads-title">Downloads &amp; Assets</h2>
        <p className="downloads-meta">Community-made anniversary assets, free to use and share.</p>
        <div className="download-grid">
          {DOWNLOADS.map((d, i) => (
            <a className="download-item" key={i}>
              <div className="download-name">{d.name}</div>
              <div className="download-desc">{d.desc}</div>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}

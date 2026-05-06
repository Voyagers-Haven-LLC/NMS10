import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'

const SOURCES = [
  { value: 'all', label: 'All sources' },
  { value: 'twitter', label: 'Twitter / X' },
  { value: 'bluesky', label: 'Bluesky' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'reddit', label: 'Reddit' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'discord', label: 'Discord' },
]

const SOURCE_BADGE = {
  twitter: '𝕏 Twitter',
  bluesky: '☁ Bluesky',
  youtube: '▶ YouTube',
  reddit: '↗ Reddit',
  discord: '◆ Discord',
  tiktok: '♪ TikTok',
}

function timeAgo(iso) {
  if (!iso) return ''
  const ts = new Date(iso)
  if (isNaN(ts.getTime())) return ''
  const diff = (Date.now() - ts.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
  return `${Math.floor(diff / 86400)} days ago`
}

function PostCard({ post }) {
  const initials = (post.author_name || '?').slice(0, 2).toUpperCase()
  return (
    <a
      className="post-card"
      href={post.external_url || '#'}
      target="_blank"
      rel="noreferrer"
      data-source={post.source}
    >
      <div className="post-header">
        <div className="post-avatar">{initials}</div>
        <div className="post-author">
          <div className="post-author-name">{post.author_name}</div>
          <div className="post-author-handle">{post.author_handle}</div>
        </div>
        <span className={`source-badge ${post.source}`}>{SOURCE_BADGE[post.source] || post.source}</span>
      </div>
      <div className="post-content">{post.content}</div>
      {post.media_path && (
        <div className="post-media">
          <img
            src={post.media_path}
            alt=""
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </div>
      )}
      <div className="post-footer">
        <span>{timeAgo(post.posted_at)}</span>
        <span className="post-link">Open →</span>
      </div>
    </a>
  )
}

export default function Socials() {
  const [posts, setPosts] = useState([])
  const [source, setSource] = useState('all')

  useEffect(() => {
    api('/socials').then(setPosts).catch(() => setPosts([]))
  }, [])

  const filtered = useMemo(
    () => posts.filter((p) => source === 'all' || p.source === source),
    [posts, source]
  )

  return (
    <div className="container">
      <div className="page-header">
        <div className="page-eyebrow">// Live Signal</div>
        <h1 className="page-title">#NMS10 Across the Stars</h1>
        <div className="page-meta">Aggregated posts from the community · Updated regularly</div>
      </div>

      <div className="socials-notice">
        <strong>Heads up:</strong> the social scrapers aren't live yet. The posts below are seeded
        placeholders curated by the team. Once Bluesky/YouTube/Reddit/Twitter/Instagram pull-jobs
        ship, this feed populates automatically.
      </div>

      <div className="filter-section">
        <div className="filter-section-label">Source</div>
        <div className="filter-bar" data-filter-group="feed">
          {SOURCES.map((s) => (
            <button
              key={s.value}
              className={`filter-chip${source === s.value ? ' active' : ''}`}
              onClick={() => setSource(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="social-wall">
        {filtered.length === 0 ? (
          <div className="no-results show">No posts match this filter.</div>
        ) : (
          filtered.map((p) => <PostCard key={p.id} post={p} />)
        )}
      </div>
    </div>
  )
}

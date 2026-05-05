# NMS10 Site — Deployment Roadmap

**From:** v9 single-file mockup → live production site
**Hard launch target:** ~July 9, 2026 (one month before anniversary)
**Lifespan:** Live through end of 2026, then archive
**Built parallel to:** Haven Phase 2A security hardening

---

## Locked architectural decisions

| Decision | Locked answer |
|---|---|
| Domain | Brand new domain (TBD — register before Phase 1 starts) |
| Host | Pi 8GB, separate Docker container alongside Haven |
| Repo | New private repo, not part of Master-Haven |
| Frontend | Full React + Vite |
| Database | SQLite, dedicated to NMS10 (separate file from Haven's DB) |
| Database long-term | After event, Haven Control Room reads NMS10's SQLite and ingests selectively. NMS10's schema is whatever fits NMS10 best. |
| Submissions | Web form on the site **+** Discord bot command, both hit the same backend queue |
| Moderation | In-site admin panel, login required, separate from Haven's auth |
| Notifications | Discord bot for new bases, new social posts, new meetups |
| Social aggregation | Self-hosted scrapers polling `#NMS10` (Bluesky/YouTube/Reddit free APIs, Twitter via Nitter+burner, Instagram via Instaloader, TikTok manual via Discord) |
| Steam player count | Steam Web API, free key, game ID 275850 |
| Fonts | Self-hosted NMSGeoSans + NMSFuturaProBook (already embedded in mockup, will move to /public/fonts/) |

---

## Stack overview

```
┌──────────────────────────────────────────────────────────┐
│ Pi 8GB · Docker host (10.0.0.33)                         │
│                                                          │
│  ┌─────────────────┐    ┌─────────────────┐             │
│  │ Haven Container │    │ NMS10 Container │             │
│  │  (existing)     │    │  (new)          │             │
│  └─────────────────┘    └─────────────────┘             │
│                              │                           │
│         ┌───────────────────┼───────────────────┐       │
│         │                   │                   │       │
│  ┌──────▼──────┐    ┌──────▼──────┐     ┌─────▼─────┐  │
│  │ FastAPI app │    │ Vite static │     │ Scrapers  │  │
│  │ (backend)   │    │ build       │     │ (cron)    │  │
│  └─────────────┘    └─────────────┘     └───────────┘  │
│         │                                       │       │
│         └────────────┐                          │       │
│                      ▼                          │       │
│             ┌────────────────┐                  │       │
│             │ nms10.db       │◄─────────────────┘       │
│             │ (SQLite)       │                          │
│             └────────────────┘                          │
│                                                          │
│  ┌──────────────────────────┐                           │
│  │ Nginx Proxy Manager      │  (existing on Pi)         │
│  │ Routes: nms10.<domain>   │                           │
│  └──────────────────────────┘                           │
└──────────────────────────────────────────────────────────┘
```

**Backend service (FastAPI)** owns:
- Public read API (bases, communities, meetups, social cache)
- Submission API (web form + Discord bot both POST here)
- Admin API (moderation, edit, delete — auth-gated)
- Steam count proxy (cached, refreshed every minute)

**Scraper services** run on cron inside the same container:
- Each social platform = one scraper script
- Run every 5–30 min depending on platform
- Insert new posts into `social_posts` table
- Fire Discord webhook on new post

**Frontend (Vite/React)** builds to static files. Nginx serves them. React Router handles client-side routing. All dynamic data comes from the FastAPI backend.

**Discord bot** runs as a separate process (or its own small container). Listens for `/submit-base` slash commands, posts notifications to designated channels.

---

# Full phase plan

## Phase 1 — MVP launch path (the build sprint)

**Goal:** Site is publicly live with all v9 mockup features running on real data, plus the bare minimum backend for submissions and scraping. Target: 1-month-pre-launch (~July 9, 2026).

### 1.1 — Infrastructure setup (Week 1)

| Task | Detail |
|---|---|
| Register domain | Namecheap. Point A record at Pi public IP, configure Cloudflare DNS proxy. |
| Set up Cloudflare | Same pattern as havenmap.online — proxy on, SSL Full (strict). |
| Create new GitHub repo | Private. `nms10-site` or similar. |
| Initialize Vite + React project | `npm create vite@latest nms10 -- --template react`. Add React Router, basic routes. |
| Initialize FastAPI project | Mirror Haven's project layout. `app/main.py`, `app/db.py`, `app/routers/`, `app/scrapers/`. |
| Create SQLite schema | See **Schema** section below. |
| Dockerize | One Dockerfile per service (backend, frontend build, scraper, bot). One docker-compose.yml. |
| Configure Nginx Proxy Manager | New host entry for the new domain → Pi container ports. Let's Encrypt cert. |
| Confirm Tailscale dev access | Claude Code SSH in via Tailscale, push/pull working. |

### 1.2 — Port the v9 mockup to React (Week 1–2)

The v9 file becomes the visual reference. The React app rebuilds it as components.

| Component | What it is |
|---|---|
| `<Layout>` | Sticky header, footer, view switching |
| `<Expedition>` | Landing page, milestone grid, reward card |
| `<MilestoneCard>` | One milestone with click-to-claim, localStorage state |
| `<Countdown>` | Big countdown for expedition page |
| `<MiniCountdown>` | Header version for other pages |
| `<CivsAndBases>` | Tab switcher, communities directory, bases grid |
| `<BaseCard>` / `<BaseDetail>` | Base showcase + detail view |
| `<Meetups>` | Map (Leaflet) + list, region filter |
| `<Socials>` | Aggregated post grid |
| `<FAQ>` | Accordion + downloads section |

**Routing (React Router):**
- `/` → Expedition
- `/civs` → Civs+Bases
- `/civs/bases/:id` → Base detail
- `/meetups` → Meetups
- `/socials` → Socials
- `/faq` → FAQ
- `/admin` → Admin login (stub for now)

**Data sources during this phase:** all data still hardcoded JSON files in `src/data/`. Real DB integration comes in 1.3.

### 1.3 — Backend API (Week 2–3)

FastAPI endpoints that match the React app's data needs.

```
GET  /api/health                       → health check
GET  /api/bases?platform=&tags=        → list bases (public)
GET  /api/bases/:id                    → single base detail
POST /api/bases                        → submit base (queued for moderation)
GET  /api/communities                  → list participating communities
GET  /api/meetups?region=              → list meetups
POST /api/meetups                      → submit meetup
GET  /api/socials?source=              → cached aggregated posts
GET  /api/steam-count                  → live player count (proxied + cached)

# Admin (auth required)
POST /api/admin/login                  → returns JWT
GET  /api/admin/queue                  → pending submissions
POST /api/admin/bases/:id/approve      → approve and publish
POST /api/admin/bases/:id/reject       → reject
PUT  /api/admin/bases/:id              → edit
DELETE /api/admin/bases/:id            → remove
# (same for meetups, communities, socials)
```

Auth: JWT with bcrypt-hashed admin password stored in env var. Single admin user for v1, multi-user comes later if needed.

### 1.4 — Scrapers (Week 3)

Each platform is its own Python module under `app/scrapers/`. APScheduler runs them on a schedule. All write to `social_posts` table with deduplication on `(source, external_id)`.

| Platform | Schedule | Method |
|---|---|---|
| Bluesky | Every 5 min | Public AT Protocol API, no auth |
| YouTube | Every 30 min | YouTube Data API v3, free key, search by `#NMS10` |
| Reddit | Every 10 min | Reddit OAuth (script app, free), search `#NMS10` in r/NoMansSkyTheGame |
| Twitter | Every 30 min | Self-hosted Nitter container + burner account session token |
| Instagram | Every 30 min | Instaloader, anonymous, hashtag query |
| TikTok | Manual | Discord bot — paste link in `#nms10-submissions` |

**On new post detected:**
1. Insert into `social_posts` table
2. Download preview image to `/data/feed-media/{id}.jpg` (or use Open Graph for link-only posts)
3. Fire Discord webhook with summary

### 1.5 — Discord bot (Week 3)

Separate Node.js (discord.js v14, matches viobot stack) or Python (discord.py) — picking the same as viobot lets you reuse patterns.

**Slash commands:**
- `/submit-base` — opens modal for base details, posts to `POST /api/bases`
- `/submit-meetup` — opens modal for meetup details, posts to `POST /api/meetups`

**Notification channels:**
- New base submitted (admin channel) — pings moderators to review
- New base approved (public channel) — announces to community
- New social post detected (public channel)
- New meetup added (public channel)

### 1.6 — Admin panel (Week 4)

React routes under `/admin/*`. Login → moderation queue → approve/reject/edit each pending submission. Simple, functional, ugly is fine.

### 1.7 — End-to-end test + bug bash (Week 4)

- Submit a test base via web form → appears in admin queue → approve → appears on public site → Discord webhook fires
- Same for meetup
- Each scraper produces at least one real post in the feed
- Steam count refreshes
- Countdown ticks correctly
- Milestone progress persists in localStorage
- Mobile layouts work

### 1.8 — Soft launch (Week 5–6)

Site goes live but unannounced. Watcher and 5–10 trusted testers from the NMS10 collaborative bang on it for a week. Bugs filed in GitHub issues.

### 1.9 — Hard launch (~July 9, 2026)

Public announcement, share on Discord, X, Bluesky, Reddit. Site goes live officially, one month before the anniversary.

---

## Phase 2 — Anniversary window (July → Aug 9)

**Goal:** Keep the site stable and responsive while the community uses it daily.

| Task | Why |
|---|---|
| Monitoring | Uptime Kuma checks the site every 60s, Discord alert on outage |
| Backups | Daily `nms10.db` snapshot to USB SSD (rolls into Haven's backup pattern) |
| Scraper health | If a scraper fails 3x in a row, Discord alerts admin |
| Submission spike handling | Expect heavy submission load in last 2 weeks. Pre-approve trusted submitters? |
| Moderation rota | Watcher/Stars/whoever else has admin access agree on a coverage schedule |
| Real-time tweaks | Performance, mobile fixes, content adjustments based on community feedback |

**Aug 9, 2026 — anniversary day:**
- Countdown auto-flips to Anniversary Day mode at 18:00 UTC
- Steam count expected to spike — make sure cache holds up
- Live updates to feed throughout the day

## Phase 3 — Post-event (Aug 10 → Dec 31)

| Task | When |
|---|---|
| Stop active scraping | Aug 31. Feed becomes static archive. |
| Lock submissions | Sept 1. No new bases/meetups, but existing entries stay browsable. |
| Anniversary recap content | Sept. "What we did" page summarizing the celebration. |
| Read-only mode | Oct. Disable admin panel writes. Site becomes a permanent archive. |
| Haven ingest | When you trigger it. Haven Control Room reads `nms10.db`, copies relevant bases into Haven's tables with NMS10 event tag. |
| Sunset planning | Dec. Site stays up but unmaintained, or hand off to community archive. |

## Phase 4 — Optional follow-on

- Persistent NMS10 archive (read-only, lives forever as a memorial of the event)
- Integration of the meetups system into Haven Control Room as a generic feature
- Open-sourcing the codebase as a template for future anniversary events (NMS11, etc.)

---

# Database schema (SQLite)

```sql
-- Bases submitted for the anniversary event
CREATE TABLE bases (
  id TEXT PRIMARY KEY,                  -- slug like 'glass-atlas'
  title TEXT NOT NULL,
  builder_name TEXT NOT NULL,
  builder_affiliation TEXT,             -- "Voyager's Haven", etc.
  description TEXT,
  builder_notes TEXT,
  platform TEXT,                        -- pc | ps | xbox | switch
  galaxy TEXT,
  region TEXT,
  class TEXT,
  portal_address TEXT,
  tags TEXT,                            -- space-separated list
  hero_image_path TEXT,                 -- /data/base-media/{id}/hero.jpg
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved_at TIMESTAMP,                -- null = still in queue
  status TEXT DEFAULT 'pending',        -- pending | approved | rejected
  submitter_email TEXT,                 -- for follow-up if needed
  submitter_discord_id TEXT,
  view_count INTEGER DEFAULT 0,
  star_count INTEGER DEFAULT 0
);

-- Photo gallery for each base (separate table because many photos per base)
CREATE TABLE base_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  base_id TEXT REFERENCES bases(id),
  image_path TEXT,
  caption TEXT,
  display_order INTEGER
);

-- Participating communities directory
CREATE TABLE communities (
  id TEXT PRIMARY KEY,                  -- slug
  name TEXT NOT NULL,
  language TEXT,                        -- "English", "Français", etc.
  description TEXT,
  link_url TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved BOOLEAN DEFAULT 0
);

-- IRL meetups
CREATE TABLE meetups (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  region TEXT,                          -- europe | north-america | asia-pacific | south-america
  location TEXT,                        -- "London, UK"
  latitude REAL,
  longitude REAL,
  starts_at TIMESTAMP,
  description TEXT,
  organizer_name TEXT,
  contact_url TEXT,
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved BOOLEAN DEFAULT 0
);

-- Aggregated social posts from scrapers
CREATE TABLE social_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,                 -- twitter | bluesky | youtube | reddit | tiktok | discord
  external_id TEXT NOT NULL,            -- platform's own ID
  author_name TEXT,
  author_handle TEXT,
  author_avatar_path TEXT,
  content TEXT,
  media_path TEXT,                      -- local cached preview
  external_url TEXT,                    -- back to the original
  posted_at TIMESTAMP,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  featured BOOLEAN DEFAULT 0,
  hidden BOOLEAN DEFAULT 0,             -- moderation
  UNIQUE(source, external_id)           -- dedup key
);

-- Admin users (just one for v1 most likely)
CREATE TABLE admin_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Steam count cache (1 row, updated every minute)
CREATE TABLE steam_cache (
  id INTEGER PRIMARY KEY,
  player_count INTEGER,
  fetched_at TIMESTAMP
);

CREATE INDEX idx_bases_status ON bases(status);
CREATE INDEX idx_bases_platform ON bases(platform);
CREATE INDEX idx_social_posts_source ON social_posts(source);
CREATE INDEX idx_social_posts_posted ON social_posts(posted_at);
CREATE INDEX idx_meetups_region ON meetups(region);
```

---

# Risks and decision points

## Things that could break

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Twitter/Nitter scraping breaks** | High — Nitter instances die regularly, X changes constantly | Have manual-link-submission fallback ready in Discord. Don't make Twitter scraping critical-path. |
| **Burner accounts get banned** | Medium-high during event peak | Have 2–3 burners ready, rotate when one dies. Document the rotation steps. |
| **Instagram rate limits** | Low at our volume | Already verified 2 req/hour vs 200/hour cap. Plenty of headroom. |
| **Submission spam after launch** | Medium | Moderation queue catches everything before public. Add basic rate limit (5 submissions per IP per hour). |
| **DDOS / unwanted attention** | Low | Cloudflare proxy already does basic protection. If serious, enable Cloudflare's "Under Attack" mode. |
| **Steam API outage on Aug 9** | Low | Cache last known count. Show "(last updated X min ago)" if stale. |
| **Pi hardware failure during event** | Low but catastrophic | USB SSD daily backups. Worst case, rebuild on another Pi from latest snapshot. |
| **Aug 9 traffic spike crashes the site** | Medium | Static frontend serves easily. Backend bottleneck is only if everyone submits simultaneously. Caching + rate limiting fixes this. |

## Decision points along the way

These are calls you'll have to make as we go. Not pre-decidable.

| Decision | When it comes up |
|---|---|
| Domain name | Before Phase 1 starts |
| Admin password / who has access | Before admin panel ships |
| Discord channel structure for notifications (one channel? per-event-type?) | Before bot deploys |
| Should communities self-edit their entry, or admin-only? | Phase 1.6 |
| Pre-approve trusted submitters to skip queue? | Phase 2 if queue gets busy |
| Stars/Watcher get admin access too, or just you? | Before launch |
| Public stats page (X bases / Y meetups / Z posts) live or no? | Late Phase 1 |
| Submissions close date — when do we lock new bases? | August, decide closer to event |
| Haven ingest happens when? Manual vs automatic? | Phase 3 |

## Things that depend on other people

These are blockers I can't unblock for you:

| Blocked on | Who |
|---|---|
| Final milestone icons (Nerozii is making them) | Nerozii |
| Final logo + downloadable assets | Mr Sinister + Dashboard Devil |
| Final FAQ content | la Checktitude / NMS10 collaborative |
| Curated list of communities | NMS10 collaborative |
| had's HTML+CSS expedition template | had |
| DreamingFox card generator integration | DreamingFox |
| Logo tutorial videos (English + French) | Dashboard Devil + la Checktitude |

**My recommendation:** ship Phase 1 with placeholders for all of these. Real assets drop in over time without breaking anything.

## Phase 2A coordination

Haven's Phase 2A is the security hardening sprint that's been pending since April. It blocks anything *Haven*-public, but it does not block NMS10 because NMS10 is in its own container with its own DB and its own auth.

**However** — Phase 2A items 4 (USB SSD backups) and 5 (Pi-hole, local DNS) directly benefit NMS10:

- The USB SSD backup cron should include `nms10.db` from day one
- Pi-hole / local DNS makes dev workflow cleaner

**Recommendation:** finish Phase 2A items 1–4 (private repo, key rotation, SSH hardening, firewall, backups) before NMS10 hits public. Items 5–6 (Pi-hole, DDNS) can land in parallel with NMS10 dev. The single biggest issue — public repo with exposed keys — has to be fixed before any new project ships.

---

# What I'd want from you to start Phase 1

Not asking you to answer all of these tonight. These are the unblockers needed before Week 1 of Phase 1 can start.

1. Domain name picked and registered
2. Phase 2A item 1 done (private repo, keys rotated) — if not, NMS10 starts as a private repo from day one and we still need this for Haven before Aug
3. Cloudflare account access confirmed
4. Watcher / NMS10 organizers know we're starting and what they're responsible for delivering
5. A `nms10` Discord channel ready for bot notifications
6. Decision: who else gets admin access on the live site (just you, or you+Stars, etc.)

When you're ready to start, I'll write the actual implementation tasks for Phase 1.1 as discrete Claude Code execution steps you can run from VS Code. That's the next deliverable after this roadmap, when you say go.

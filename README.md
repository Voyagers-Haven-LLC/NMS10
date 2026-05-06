# NMS10 Site

Anniversary site for the NMS10 community celebration of No Man's Sky's 10th anniversary (Aug 9, 2026). Built under Voyager's Haven LLC, separate from Haven Control Room.

**Hard launch target:** ~July 9, 2026 (one month before anniversary)
**Lifespan:** Live through end of 2026, then archive.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + Vite, React Router, Leaflet |
| Backend | FastAPI, SQLAlchemy core, APScheduler |
| Database | SQLite (`/data/nms10.db`) |
| Auth | bcrypt + JWT (single admin) |
| Scrapers | Python modules (stubs), to be scheduled later inside backend container |
| Bot | Discord bot (later session) |
| Deploy | Docker Compose on Pi 8GB, behind Nginx Proxy Manager |

## Repo layout

```
/frontend     React + Vite app
/backend      FastAPI app, schema, auth, seed, Steam fetcher
/scrapers     Python scraper module stubs (Bluesky, YouTube, Reddit, Twitter, Instagram)
/bot          Discord bot stub
/docker       Dockerfiles + docker-compose.yml (TBD)
/docs         Roadmap + v9 mockup reference
/data         SQLite DB + uploaded images (gitignored)
```

## Local development

### Backend

```bash
cd backend
py -3 -m venv .venv
.venv\Scripts\activate                           # Windows PowerShell / cmd
# source .venv/bin/activate                      # macOS/Linux/Git Bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/api/health
# → http://127.0.0.1:8000/docs   (Swagger UI)
```

On first start, the backend will:
1. Create the SQLite schema in `data/nms10.db`.
2. Bootstrap the admin user from env vars (see below).
3. Seed the v9 sample data (6 bases, 6 communities, 9 meetups, 6 socials).
4. Pull the live Steam concurrent player count and refresh every 60s.

To re-seed from scratch, delete `data/nms10.db` and restart.

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Vite proxies `/api/*` and `/media/*` to the backend on `:8000`.

## Routes

| Path | Purpose |
|---|---|
| `/` | Expedition landing — countdown, 8 milestones (localStorage), reward |
| `/civs` | Communities + Bases tabs, filter chips, submission forms |
| `/civs/bases/:id` | Single base detail — gallery, builder notes, portal address |
| `/meetups` | Leaflet map + region filter, click-to-fly sync, submission form |
| `/socials` | Aggregated post grid with source filter |
| `/faq` | FAQ accordion + downloads section |
| `/admin` | Admin login (when signed out) / admin panel (when signed in) |

## Admin

Default login on a fresh DB:

- **Username:** `admin`
- **Password:** `changeme` (set `NMS10_ADMIN_PASSWORD` to override)

The admin panel covers:

- **Queue** — pending bases, communities, meetups. Approve / reject inline.
- **Bases** — full CRUD, hero image upload, gallery upload + delete.
- **Communities** — full CRUD with approved toggle.
- **Meetups** — full CRUD with click-on-map location picker.
- **Socials** — CRUD on aggregated posts (curated until scrapers ship). Toggle `featured` and `hidden`.

## Discord bot

Lives under `/bot`. Python 3.11 + discord.py 2.x. Single bot account, multi-guild.

Slash commands:

| Command | Modal fields |
|---|---|
| `/submit-base` (with `platform` choice) | title, builder, galaxy & portal, description, notes |
| `/submit-community` | name, language, link, description |
| `/submit-meetup` (with `region` choice) | title, location, lat/lng, starts-at, description |
| `/submit-social` | url + optional note (backend fetches Open Graph) |
| `/nms10-status` | countdown · Steam count · totals · 3 latest signals |
| `/bot-reload` | reload `bot/config/servers.yaml` (admin-only) |

Per-guild routing config: copy `bot/config/servers.example.yaml` to
`bot/config/servers.yaml` and fill in guild + channel IDs. `null` means
"don't post that type here." The bot reloads this file on startup and
on `/bot-reload`.

The bot exposes a loopback webhook at `http://127.0.0.1:9000/notify`. The
backend POSTs notifications there (submission / approved / new_social) and
the bot fans them out to the configured channels.

### Run the bot locally

```bash
cp bot/.env.example bot/.env       # fill in NMS10_DISCORD_BOT_TOKEN
cp bot/config/servers.example.yaml bot/config/servers.yaml
# Edit servers.yaml with your real guild + channel IDs.

# Mac/Linux/Git Bash
./bot/run-dev.sh

# Windows PowerShell
.\bot\run-dev.ps1

# Webhook-only mode (no Discord token required, useful for pipeline tests)
./bot/run-dev.sh --no-discord
```

### Bluesky scraper

`backend/app/scrapers/bluesky.py` polls the public AT Protocol search
endpoint every 5 minutes, deduplicating against `social_posts`.

```bash
# Manual one-shot for verification
cd backend
.\.venv\Scripts\python.exe -m app.scrapers.bluesky --once --json
```

Failures count up; 3+ consecutive failures auto-rebackoff to 15 min.
State is queryable at `GET /api/admin/scraper-status` (auth required).
Logs appended to `data/logs/scrapers.log`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NMS10_ADMIN_PASSWORD` | `changeme` (warning logged) | Admin password. Bcrypt-hashed on first start. |
| `NMS10_JWT_SECRET` | random secret in `data/.jwt-secret` | HMAC secret for JWTs. Set before deploy. |
| `NMS10_DATA_DIR` | `<repo>/data` | Where the SQLite DB and uploaded media live. Set to `/data` in the Docker image. |
| `STEAM_API_KEY` | (none) | Optional Steam Web API key. The endpoint we hit doesn't need it. |
| `NMS10_BOT_WEBHOOK_URL` | `http://127.0.0.1:9000/notify` | Where the backend's `notify_bot` helper POSTs. |
| `NMS10_SCRAPER_AUTO_PUBLISH` | `true` | If `true`, scraped posts are visible immediately. `false` queues them. |
| `NMS10_DISCORD_BOT_TOKEN` | (none) | **Bot:** Discord bot token. Required to connect to Discord. |
| `NMS10_BOT_ADMINS` | (empty) | **Bot:** comma-separated Discord user IDs allowed to run `/bot-reload`. |
| `NMS10_BACKEND_URL` | `http://localhost:8000` | **Bot:** where to find the backend API. |
| `NMS10_BOT_WEBHOOK_HOST` | `127.0.0.1` | **Bot:** webhook bind host. `0.0.0.0` inside Docker compose so the backend container can reach it. |
| `NMS10_BOT_WEBHOOK_PORT` | `9000` | **Bot:** webhook listen port. |

The backend logs a warning at startup if `NMS10_ADMIN_PASSWORD` or
`NMS10_JWT_SECRET` are unset.

## Docker

```bash
cp bot/.env.example .env       # fill in NMS10_DISCORD_BOT_TOKEN at minimum
docker compose up --build
```

This brings up `nms10-backend` (published on host port 8000) and
`nms10-bot` (no published ports — the webhook is internal-only). The
backend's data volume `nms10-data` persists the SQLite DB and uploaded
media across restarts.

## Reference

- Roadmap: [`docs/nms10-roadmap.md`](docs/nms10-roadmap.md)
- Visual reference: [`docs/nms10-mockup-v9.html`](docs/nms10-mockup-v9.html)

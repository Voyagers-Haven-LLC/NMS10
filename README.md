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

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NMS10_ADMIN_PASSWORD` | `changeme` (warning logged) | Admin password. Bcrypt-hashed on first start; rotated automatically if you change this. |
| `NMS10_JWT_SECRET` | random secret stored in `data/.jwt-secret` | HMAC secret for signed JWTs. Set explicitly before deploying. |
| `STEAM_API_KEY` | (none) | Optional. The public Steam endpoint we hit doesn't require a key, but if Valve ever rate-limits us we'll add it via this var. |

The backend logs a warning at startup if either of the first two are unset.

## Reference

- Roadmap: [`docs/nms10-roadmap.md`](docs/nms10-roadmap.md)
- Visual reference: [`docs/nms10-mockup-v9.html`](docs/nms10-mockup-v9.html)

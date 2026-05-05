# NMS10 Site

Anniversary site for the NMS10 community celebration of No Man's Sky's 10th anniversary (Aug 9, 2026). Built under Voyager's Haven LLC, separate from Haven Control Room.

**Hard launch target:** ~July 9, 2026 (one month before anniversary)
**Lifespan:** Live through end of 2026, then archive.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + Vite, React Router, Leaflet |
| Backend | FastAPI, SQLAlchemy, APScheduler |
| Database | SQLite (`/data/nms10.db`) |
| Scrapers | Python modules, scheduled inside backend container |
| Bot | Discord bot (Node or Python — TBD) |
| Deploy | Docker Compose on Pi 8GB, behind Nginx Proxy Manager |

## Repo layout

```
/frontend     React + Vite app
/backend      FastAPI app + SQLAlchemy schema
/scrapers     Python scraper module stubs (Bluesky, YouTube, Reddit, Twitter, Instagram)
/bot          Discord bot stub
/docker       Dockerfiles + docker-compose.yml (TBD)
/docs         Roadmap, design notes, mockup reference
```

## Local development

### Backend

```bash
cd backend
py -3 -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/api/health
```

The DB file is created on first startup at `<repo>/data/nms10.db` and the schema is applied automatically.

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

Routes scaffolded so far:

| Path | Purpose |
|---|---|
| `/` | Expedition landing |
| `/civs` | Civs + Bases directory |
| `/civs/bases/:id` | Single base detail |
| `/meetups` | IRL meetups map + list |
| `/socials` | Aggregated social feed |
| `/faq` | FAQ + downloads |
| `/admin` | Admin login / moderation |

All routes are placeholders — the v9 mockup port happens in a later session.

## Reference

- Roadmap: [`docs/nms10-roadmap.md`](docs/nms10-roadmap.md)
- Visual reference: [`docs/nms10-mockup-v9.html`](docs/nms10-mockup-v9.html)

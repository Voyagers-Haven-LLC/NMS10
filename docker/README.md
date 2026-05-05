# Docker

Dockerfiles + `docker-compose.yml` will land here once the backend and frontend run reliably in dev. See roadmap Phase 1.1 — "Dockerize" task.

Planned services:

- `backend` — FastAPI + APScheduler-driven scrapers
- `frontend-build` — Vite static build, served by nginx (or Nginx Proxy Manager directly)
- `bot` — Discord bot (separate process)

Routed by Nginx Proxy Manager already running on the Pi.

# nms10 — Claude context

NMS companion app (nms10.online). Three-container stack in one compose. Standalone repo in the Voyagers-Haven-LLC org (currently PUBLIC).

## Layout
- `backend/` — API service (`nms10-backend`).
- `frontend/` — web (`nms10-frontend`).
- `bot/` — Discord bot (`nms10-bot`).
- `docker-compose.yml` defines all three + the `nms10-data` volume.

## Deploy / ops
- Pi: `~/docker/nms10`. Because it's 3 services, the generic single-service `auto-deploy.sh` can't rebuild them — a custom `~/scripts/nms10-deploy.sh` (`*/2` cron) does `docker compose up -d --build` (all three) on any push.
- Data host-mounted at `~/docker/nms10-data`.

## Gotchas
- Editing any of backend/frontend/bot and pushing rebuilds all three (Docker cache no-ops the untouched ones).

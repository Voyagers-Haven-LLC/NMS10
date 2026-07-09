# NMS10 (nms10)

No Man's Sky companion web app + Discord bot.

Part of the Voyagers-Haven-LLC modular org — see the [Master-Haven super-repo](https://github.com/Voyagers-Haven-LLC/Master-Haven).

## Stack
`backend/` (API) · `frontend/` (web) · `bot/` (Discord) — three containers via one compose.

## Live
- **nms10.online** — containers `nms10-frontend` (host `8090`), `nms10-backend` (host `8000`), `nms10-bot`. NPM routes the domain to the frontend.

## Deploy
Push to `main` → the Pi's `*/2` **`nms10-deploy.sh`** cron pulls + runs `docker compose up -d --build` (rebuilds all three containers). Runs from `~/docker/nms10`; data in host mount `~/docker/nms10-data`.

## Local dev
`docker compose up --build` from the repo root brings up all three services.

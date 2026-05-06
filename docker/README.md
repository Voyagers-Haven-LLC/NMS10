# Docker

Two services, one network, one persistent volume.

| Service | Image tag | Port | Notes |
|---|---|---|---|
| `nms10-backend` | `nms10-backend:local` | host **8000** | FastAPI + scheduler + scrapers |
| `nms10-bot` | `nms10-bot:local` | internal **9000** | Discord bot + webhook receiver |

The bot reaches the backend at `http://nms10-backend:8000` over the
internal compose network. The backend reaches the bot at
`http://nms10-bot:9000/notify`. **Neither port is exposed to the public
internet** — only the host machine can reach the backend on port 8000,
and that's expected to sit behind Nginx Proxy Manager once you deploy.

## Persistent volume

`nms10-data` is a named Docker volume mounted at:

| Mount | Container | Purpose |
|---|---|---|
| `nms10-data:/data` | backend (rw) | SQLite DB, backups, scraper logs, JWT secret, bot-internal-secret |
| `nms10-data:/data:ro` | bot (read-only) | reads `.bot-internal-secret` for the rate-limit bypass header |

The volume survives `docker compose down`. Use `docker compose down -v` to
wipe it (don't, unless you mean it).

## Local run

```bash
# Build + bring up everything
docker compose up --build -d

# Tail logs
docker compose logs -f

# Trigger a manual backup inside the running backend container
docker compose exec nms10-backend python -m scripts.backup_db

# Hit the API from the host
curl http://localhost:8000/api/health
```

The first time you `up`, the backend auto-generates:

- `data/.jwt-secret` — JWT signing key for admin sessions
- `data/.bot-internal-secret` — shared secret with the bot for rate-limit bypass
- `data/backups/nms10-<timestamp>.db` — first-boot snapshot

Subsequent restarts reuse the same values from the volume.

## Required environment variables

Compose reads these from a `.env` file at the repo root if present, or
from your shell. **None of them is technically required** — the stack
boots end-to-end with safe defaults — but you'll want to set most of them
in production.

```bash
# Copy a starting point and edit
cp backend/.env.example .env
```

The variables compose looks for:

| Variable | Default in compose | Why you'd set it |
|---|---|---|
| `NMS10_ADMIN_PASSWORD` | `changeme` | Pick a real password |
| `NMS10_JWT_SECRET` | auto-generated | Pin it across restarts (otherwise admin sessions invalidate on every boot if you don't have the volume) |
| `NMS10_DISCORD_BOT_TOKEN` | (empty → bot runs in webhook-only mode) | Real Discord login |
| `NMS10_BOT_ADMINS` | (empty) | Comma-separated Discord user IDs for `/bot-reload` |
| `NMS10_SITE_URL` | `http://localhost:5173` | Real public URL once you have one |
| `NMS10_SUBMISSION_RATE_LIMIT` | `5/hour` | Override per-IP submission limit |
| `NMS10_SCRAPER_AUTO_PUBLISH` | `false` | Flip to `true` only if you trust the per-source filters fully |
| `YOUTUBE_API_KEY` | `STUB` | Real YouTube Data API v3 key |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | `STUB` | Real Reddit script-app creds (or leave STUB → unauth fallback) |
| `REDDIT_USER_AGENT` | `nms10-aggregator/1.0 (by /u/Parker1920)` | Reddit's API rules require this |
| `TWITTER_AUTH_TOKEN` | `STUB` | Burner X account `auth_token` cookie |
| `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD` | `STUB` | Burner Instagram creds |
| `STEAM_API_KEY` | (empty) | Optional — public endpoint we hit doesn't require it |

## Healthcheck

The backend has a built-in healthcheck at `/api/health`. The bot
`depends_on` it being healthy before starting, so on `up` you'll see:

```
Container nms10-backend  Started
Container nms10-backend  Waiting       (~10–30s for healthcheck to pass)
Container nms10-backend  Healthy
Container nms10-bot      Starting
Container nms10-bot      Started
```

If the backend is unhealthy after 30s + 5 retries, `compose up` will give
up. Tail the logs with `docker compose logs nms10-backend` to see why.

## Validate after a fresh build

```bash
# Compose came up clean
docker compose ps          # both Up, backend (healthy)

# Backend serves
curl http://localhost:8000/api/health

# Bot reads the shared secret
docker compose exec nms10-bot python -c "from bot.app_config import BOT_INTERNAL_SECRET; print(len(BOT_INTERNAL_SECRET))"

# Backup mechanism works inside the container
docker compose exec nms10-backend python -m scripts.backup_db
docker compose exec nms10-backend ls /data/backups
```

## Deploy notes for the Pi (later)

- Nginx Proxy Manager already runs on the host. Add a proxy host pointing
  at `127.0.0.1:8000` for the public NMS10 domain, with Let's Encrypt SSL.
- The bot needs an outbound connection to Discord's gateway and CDN. No
  inbound exposure.
- For the volume, you'll probably want to bind-mount `/srv/nms10/data`
  instead of using a Docker named volume, so the data is easy to back up
  to USB SSD per the roadmap. Override the `volumes:` block in a
  `docker-compose.override.yml` rather than editing the main compose file.

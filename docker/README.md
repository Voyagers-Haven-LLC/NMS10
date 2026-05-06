# Docker

Two services, one network.

| Service | Image | Port |
|---|---|---|
| `nms10-backend` | built from [`backend.Dockerfile`](backend.Dockerfile) | host 8000 (published) |
| `nms10-bot` | built from [`bot.Dockerfile`](bot.Dockerfile) | 9000 (internal only) |

The bot reaches the backend via `http://nms10-backend:8000`. The backend
reaches the bot via `http://nms10-bot:9000/notify`. Neither endpoint is
exposed to the public internet — the bot's webhook is internal-only by
design, and the backend's port is published only to the host (Pi's local
network), expecting Nginx Proxy Manager in front of it for TLS.

## Local run

```bash
cp .env.example .env       # then fill in NMS10_DISCORD_BOT_TOKEN etc.
docker compose up --build
```

The backend's data volume (`nms10-data`) holds `nms10.db`, uploaded base
images, and scraped social media. The compose volume persists across
restarts. `docker compose down -v` wipes it.

## Deploy notes for the Pi

- Nginx Proxy Manager already runs on the host. Add a proxy host pointing
  at `127.0.0.1:8000` for the public NMS10 domain, with Let's Encrypt SSL.
- The bot needs an outbound connection to Discord's gateway and CDN. No
  inbound exposure.
- Consider running compose with `--profile prod` once we add per-env
  overrides (currently single profile).

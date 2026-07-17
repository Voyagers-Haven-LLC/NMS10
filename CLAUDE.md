# nms10 — Claude context

NMS companion app (**nms10.online**). A **three-container** stack (backend + frontend + bot) in one compose. Org repo; currently **public**.

## Layout
- `backend/` (`nms10-backend`, host `8000`) · `frontend/` (`nms10-frontend`, host `8090`) · `bot/` (`nms10-bot`, Discord).
- `docker-compose.yml` defines all three + the `nms10-data` volume.

## Deploy / ops
- Pi dir `~/docker/nms10`. Because it's **3 services**, the generic single-service `auto-deploy.sh` can't rebuild them — a custom script does:
  `*/2 * * * * ~/scripts/nms10-deploy.sh`  (pulls, then `docker compose up -d --build` = all three; Docker cache no-ops the untouched ones)
- Manual deploy: `ssh -i ~/.ssh/claude_pi_key pi8gb@100.79.172.115 'cd ~/docker/nms10 && git pull && docker compose up -d --build'`
- **Data:** host mount `~/docker/nms10-data`.
- Remote is `https://github.com/Voyagers-Haven-LLC/NMS10.git` (public → the Pi pulls over HTTPS, no deploy key needed).

## Connecting (Pi + GitHub)

> This repo is **private** — these operational details live here on purpose. **No keys or secrets are ever committed**; they stay in the Pi's gitignored `.env` files and `~/.ssh/`.

**SSH to the Pi (production host):**
```bash
ssh -i ~/.ssh/claude_pi_key -o StrictHostKeyChecking=accept-new -o BatchMode=yes pi8gb@100.79.172.115
```
- `100.79.172.115` = **Tailscale** IP (reachable anywhere). LAN: `10.0.0.229`. Pi 5 (8 GB), user `pi8gb`.
- Every service lives in `~/docker/<service>/`; its data in `~/docker/<service>-data/` (host mounts, never in git).

**GitHub (`gh` CLI):**
- `gh` is **not on PATH** — invoke it as `"/c/Program Files/GitHub CLI/gh.exe"` (git-bash) .
- Two accounts: **`Voyagers-Haven`** (LLC; org owner; the default) and **`Parker1920`** (org owner; the *only* account with access to art3mis's `Goables/*` repos). Switch with `gh auth switch --user <name>`.
- Commit author: LLC repos → `Voyagers-Haven`; `Goables/*` repos → `Parker1920`. **Never add Claude attribution or a `Co-Authored-By` trailer.**
- The Pi pulls private org repos through **per-repo read-only deploy keys** — remotes look like `git@gh-<repo>:Voyagers-Haven-LLC/<repo>.git` (host aliases in the Pi's `~/.ssh/config`).
- Org `default_repository_permission=none`; owners are `Parker1920` + `Voyagers-Haven`.

**Verify from the Pi** (public domains must be curled *on* the Pi — Parker's LAN has no hairpin NAT):
```bash
ssh -i ~/.ssh/claude_pi_key pi8gb@100.79.172.115 'docker ps --filter name=<container>'
ssh -i ~/.ssh/claude_pi_key pi8gb@100.79.172.115 'curl -sk -o /dev/null -w "%{http_code}" --resolve <domain>:443:127.0.0.1 https://<domain>/'
```

## Serving this for Parker — tailnet URL, never localhost-only

`npm run dev` binds `0.0.0.0` (`host: true` in `frontend/vite.config.js`) on **:5173**;
it proxies `/api` + `/media` to the backend on :8000.

Hand back **`http://100.70.191.5:5173/`** — never `http://localhost:5173`. A localhost URL
is a dead end: Parker can't forward it, and re-asking for a real one burns a round-trip. Every
viewer we send to (Stars & co) is already a tailnet node, so the `100.x` URL just works.
Confirm the IP if it looks off — `"/c/Program Files/Tailscale/tailscale.exe" ip -4`
(`tailscale` is not on PATH in git-bash). Never "fix" a bind error by reverting to localhost.

Full rule + rationale: Master-Haven's `CLAUDE.md`.

## Universal gotchas
- **NPM routing:** the `npm` (Nginx Proxy Manager) container routes each domain to its container **by name** over the `docker_default` network. A compose recreate that drops the container off `docker_default` → instant 502.
- **Data never moves:** DBs/photos/backups live in host mounts. `git pull`/rebuilds must never touch them.
- **"The site is down" from Parker's Windows box** is usually *not* the server — each `*.online` domain needs a `10.0.0.229 <domain>` line in `C:\Windows\System32\drivers\etc\hosts` (no hairpin NAT). Check that first.
- **This repo's own traps:** editing any one of backend/frontend/bot rebuilds all three. NPM routes `nms10.online` to `nms10-frontend`.

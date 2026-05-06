"""Bot env-var config. Reads from process env (or .env via python-dotenv if
present). Defaults are dev-friendly so the bot can run with `--no-discord`
for local pipeline testing without a Discord token."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

BOT_DIR = Path(__file__).resolve().parent


def _read_shared_secret_file() -> str:
    """When bot + backend share the same host (dev, single-machine deploys),
    read the auto-generated rate-limit-bypass secret directly from the
    backend's data dir. NMS10_DATA_DIR wins if set, else repo-relative."""
    candidates = [
        os.environ.get("NMS10_DATA_DIR"),
        str(BOT_DIR.parent / "data"),
    ]
    for d in candidates:
        if not d:
            continue
        f = Path(d) / ".bot-internal-secret"
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
    return ""


DISCORD_TOKEN = os.environ.get("NMS10_DISCORD_BOT_TOKEN", "").strip() or None
BOT_ADMINS = {
    s.strip()
    for s in os.environ.get("NMS10_BOT_ADMINS", "").split(",")
    if s.strip()
}
BACKEND_URL = os.environ.get("NMS10_BACKEND_URL", "http://localhost:8000").rstrip("/")
SITE_URL = os.environ.get("NMS10_SITE_URL", "http://localhost:5173").rstrip("/")

# Shared secret with the backend for rate-limit bypass on submissions.
# Backend auto-generates this and persists to data/.bot-internal-secret;
# bot reads the same file when both run on the same host. Override via env
# var when running them on different hosts (Docker compose, separate Pis).
BOT_INTERNAL_SECRET = os.environ.get("NMS10_BOT_INTERNAL_SECRET", "").strip() or _read_shared_secret_file()

WEBHOOK_HOST = os.environ.get("NMS10_BOT_WEBHOOK_HOST", "127.0.0.1")
WEBHOOK_PORT = int(os.environ.get("NMS10_BOT_WEBHOOK_PORT", "9000"))
SERVERS_FILE = Path(
    os.environ.get("NMS10_BOT_SERVERS_FILE", str(BOT_DIR / "config" / "servers.yaml"))
).resolve()


def is_bot_admin(user_id: int | str) -> bool:
    return str(user_id) in BOT_ADMINS

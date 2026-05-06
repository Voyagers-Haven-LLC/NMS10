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

DISCORD_TOKEN = os.environ.get("NMS10_DISCORD_BOT_TOKEN", "").strip() or None
BOT_ADMINS = {
    s.strip()
    for s in os.environ.get("NMS10_BOT_ADMINS", "").split(",")
    if s.strip()
}
BACKEND_URL = os.environ.get("NMS10_BACKEND_URL", "http://localhost:8000").rstrip("/")
WEBHOOK_HOST = os.environ.get("NMS10_BOT_WEBHOOK_HOST", "127.0.0.1")
WEBHOOK_PORT = int(os.environ.get("NMS10_BOT_WEBHOOK_PORT", "9000"))
SERVERS_FILE = Path(
    os.environ.get("NMS10_BOT_SERVERS_FILE", str(BOT_DIR / "config" / "servers.yaml"))
).resolve()


def is_bot_admin(user_id: int | str) -> bool:
    return str(user_id) in BOT_ADMINS

"""Runtime configuration. Reads env vars with safe dev defaults so the app
boots without setup, but logs a warning when a default is used."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger("nms10.config")

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
# Allow Docker to override via NMS10_DATA_DIR=/data; otherwise sit next to the repo.
DATA_DIR = Path(os.environ.get("NMS10_DATA_DIR", str(REPO_ROOT / "data"))).resolve()
DB_PATH = DATA_DIR / "nms10.db"
MEDIA_DIR = DATA_DIR / "base-media"
JWT_SECRET_FILE = DATA_DIR / ".jwt-secret"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_DEFAULT = "changeme"
ADMIN_PASSWORD = os.environ.get("NMS10_ADMIN_PASSWORD", "").strip() or ADMIN_PASSWORD_DEFAULT
ADMIN_PASSWORD_IS_DEFAULT = ADMIN_PASSWORD == ADMIN_PASSWORD_DEFAULT


def _load_or_create_jwt_secret() -> str:
    env = os.environ.get("NMS10_JWT_SECRET", "").strip()
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if JWT_SECRET_FILE.exists():
        return JWT_SECRET_FILE.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    JWT_SECRET_FILE.write_text(secret, encoding="utf-8")
    return secret


JWT_SECRET = _load_or_create_jwt_secret()
JWT_SECRET_IS_DEFAULT = not bool(os.environ.get("NMS10_JWT_SECRET"))

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 24 * 60 * 60

STEAM_APP_ID = 275850
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "").strip() or None
STEAM_REFRESH_SECONDS = 60

# Discord bot webhook (loopback only by design)
BOT_WEBHOOK_URL = os.environ.get(
    "NMS10_BOT_WEBHOOK_URL", "http://127.0.0.1:9000/notify"
).strip()

# Scraper behavior
SCRAPER_AUTO_PUBLISH = os.environ.get("NMS10_SCRAPER_AUTO_PUBLISH", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
BLUESKY_REFRESH_SECONDS = 5 * 60        # 5 min healthy cadence
BLUESKY_BACKOFF_SECONDS = 15 * 60       # 15 min after 3+ consecutive failures
SCRAPER_LOG_DIR = DATA_DIR / "logs"
SOCIAL_MEDIA_DIR = DATA_DIR / "social-media"


def warn_defaults() -> None:
    if ADMIN_PASSWORD_IS_DEFAULT:
        logger.warning(
            "NMS10_ADMIN_PASSWORD not set — using default 'changeme'. "
            "Set this env var before deploying."
        )
    if JWT_SECRET_IS_DEFAULT:
        logger.warning(
            "NMS10_JWT_SECRET not set — using/created secret in %s. "
            "Set this env var explicitly before deploying.",
            JWT_SECRET_FILE,
        )

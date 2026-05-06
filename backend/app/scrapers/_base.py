"""Shared utilities for all scrapers.

Every scraper module imports from here. This is also where the stub-credential
gate lives, so a scraper with `STUB` env vars marks itself in the DB and skips
without crashing the scheduler.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import httpx
from sqlalchemy import text

from .. import config, scraper_status
from ..db import engine
from ..notifications import notify_bot

USER_AGENT_DEFAULT = "nms10-aggregator/1.0 (+https://github.com/Parker1920/nms10-site)"
DOWNLOAD_TIMEOUT_SECONDS = 10.0


def attach_file_logger(logger: logging.Logger) -> logging.Logger:
    """Tee scraper output to data/logs/scrapers.log so admins can tail it."""
    config.SCRAPER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.SCRAPER_LOG_DIR / "scrapers.log"
    if not any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path
        for h in logger.handlers
    ):
        h = logging.FileHandler(log_path, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


def has_stub_credentials(env_names: Iterable[str]) -> Optional[str]:
    """Return the name of the first env var that is missing or set to 'STUB'.
    None if every var has a real value."""
    for name in env_names:
        v = (os.environ.get(name) or "").strip()
        if not v or v.upper() == "STUB":
            return name
    return None


def mark_stub_skip(scraper_name: str, missing_var: str, logger: logging.Logger) -> dict:
    """Standard "I have no creds, skipping" path. Sets auth_state and returns
    a no-op summary suitable for the scraper's run() to return."""
    logger.warning(
        "scraper %s skipped: stub credentials (%s missing or set to STUB)",
        scraper_name,
        missing_var,
    )
    state = scraper_status.get(scraper_name)
    if state.auth_state != "stub-credentials":
        state.set_auth_state("stub-credentials")
    return {"ok": True, "skipped": "stub-credentials", "fetched": 0, "inserted": 0}


def mark_auth_failure(scraper_name: str, error: str, logger: logging.Logger) -> None:
    """Auth-related failure path. Records failure AND flips auth_state."""
    state = scraper_status.get(scraper_name)
    state.record_failure(error)
    state.set_auth_state("auth-failed")
    logger.error("scraper %s auth-failed: %s", scraper_name, error)


def media_extension_for(url: str, default: str = ".jpg") -> str:
    u = url.lower().split("?")[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if u.endswith(ext):
            return ".jpeg" if ext == ".jpeg" else ext
    return default


def download_media(url: str, scraper_name: str, external_id: str, logger: logging.Logger) -> Optional[str]:
    """Download a thumbnail/image to /data/social-media/{scraper}-{id}{ext}.
    Returns the public path under /media-social/... on success, None on
    failure (which is logged as a warning, not raised)."""
    if not url:
        return None
    ext = media_extension_for(url)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(external_id))[:120]
    dest = config.SOCIAL_MEDIA_DIR / f"{scraper_name}-{safe_id}{ext}"
    try:
        with httpx.Client(
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT_DEFAULT},
            follow_redirects=True,
        ) as client:
            r = client.get(url)
        if r.status_code != 200 or not r.content:
            logger.warning("media download %s -> HTTP %s", url, r.status_code)
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("media download failed %s: %s", url, exc)
        return None
    return f"/media-social/{dest.name}"


def insert_post(
    *,
    source: str,
    external_id: str,
    author_name: Optional[str],
    author_handle: Optional[str],
    content: Optional[str],
    external_url: Optional[str],
    posted_at: Optional[str],
    media_path: Optional[str] = None,
    hidden: bool = False,
) -> Optional[int]:
    """Common insert. Dedupes on (source, external_id). Returns the new
    social_posts.id, or None if the row already existed."""
    if not external_id:
        return None
    fetched_at = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM social_posts WHERE source = :s AND external_id = :e"),
            {"s": source, "e": external_id},
        ).first()
        if existing is not None:
            return None
        result = conn.execute(
            text(
                "INSERT INTO social_posts "
                "  (source, external_id, author_name, author_handle, content, "
                "   external_url, posted_at, fetched_at, media_path, featured, hidden) "
                "VALUES (:source, :external_id, :author_name, :author_handle, :content, "
                "   :external_url, :posted_at, :fetched_at, :media_path, 0, :hidden)"
            ),
            {
                "source": source,
                "external_id": external_id,
                "author_name": author_name,
                "author_handle": author_handle,
                "content": (content or "")[:2000] or None,
                "external_url": external_url,
                "posted_at": posted_at,
                "fetched_at": fetched_at,
                "media_path": media_path,
                "hidden": 1 if hidden else 0,
            },
        )
        return result.lastrowid


def attach_media(post_id: int, media_path: str) -> None:
    """Update an existing row with a media path (used after we download
    the image post-insert so the filename can include the row id)."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE social_posts SET media_path = :p WHERE id = :id"),
            {"p": media_path, "id": post_id},
        )


def fire_new_social_notification(
    *,
    post_id: int,
    source: str,
    author: Optional[str],
    content: Optional[str],
    external_url: Optional[str],
    logger: logging.Logger,
) -> bool:
    """Fire-and-forget bot notify. Returns True on dispatch, False on local error."""
    try:
        notify_bot(
            "new_social",
            {
                "id": post_id,
                "source": source,
                "author": author,
                "content": (content or "")[:280],
                "external_url": external_url,
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001 — bot is best-effort
        logger.warning("notify_bot failed: %s", exc)
        return False


def auto_publish() -> bool:
    """True = scraped posts are visible immediately. False = queued for
    moderation (hidden=true). Set by NMS10_SCRAPER_AUTO_PUBLISH env var."""
    return config.SCRAPER_AUTO_PUBLISH

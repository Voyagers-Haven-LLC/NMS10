"""Bluesky #NMS10 scraper.

Polls the public AT Protocol search endpoint, dedupes against
social_posts(source='bluesky', external_id=at_uri), and inserts new rows.
Embedded images are downloaded to data/social-media/{post_id}.jpg.

Design notes
------------
* No auth — `app.bsky.feed.searchPosts` is public.
* External id = the at:// URI (e.g. at://did:plc:.../app.bsky.feed.post/3kxx...)
  which is globally unique and stable.
* hidden flag = inverse of NMS10_SCRAPER_AUTO_PUBLISH (default: auto-publish on).
* On failure, scraper_status records the error and trips backoff at 3+
  consecutive failures (15 min instead of 5).
* The fire-and-forget bot notification only happens for visible posts
  (hidden=false), so we don't double-ping admins on a queued backlog.

Run modes
---------
* `python -m app.scrapers.bluesky --once` does one synchronous poll and exits.
  Used for verification and for ad-hoc backfill.
* When the FastAPI app is up, APScheduler calls `run()` on a 5-minute interval.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import text

from .. import config, scraper_status
from ..db import engine, init_db
from ..notifications import notify_bot

NAME = "bluesky"
SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
QUERY = "#NMS10"
PAGE_LIMIT = 50
USER_AGENT = "nms10-bot/0.1 (+https://github.com/Parker1920/nms10-site)"

logger = logging.getLogger("nms10.scraper.bluesky")


def _file_logger() -> logging.Logger:
    """Attach a per-scraper file handler the first time we run, so admins can
    tail data/logs/scrapers.log without losing output."""
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


def _post_url(handle: str, uri: str) -> str:
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def _download_image(url: str, dest: Path) -> Optional[Path]:
    try:
        with httpx.Client(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
            r = client.get(url)
            if r.status_code != 200:
                return None
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return dest
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("image download failed %s: %s", url, exc)
        return None


def _extract_first_image(post: dict) -> Optional[str]:
    """Bluesky embeds: images, external (link card), record (quote post),
    recordWithMedia. We pull from the most common shapes."""
    embed = post.get("embed") or {}
    embed_type = embed.get("$type", "")
    if "images" in embed_type or "imagesView" in embed_type:
        imgs = embed.get("images") or []
        if imgs:
            return imgs[0].get("fullsize") or imgs[0].get("thumb")
    if "external" in embed_type or "externalView" in embed_type:
        ext = embed.get("external") or {}
        return ext.get("thumb")
    if "recordWithMedia" in embed_type:
        media = embed.get("media") or {}
        imgs = media.get("images") or []
        if imgs:
            return imgs[0].get("fullsize") or imgs[0].get("thumb")
    return None


def _insert_post(post: dict, hidden: bool) -> Optional[int]:
    """Returns the new social_posts.id, or None if the post already existed."""
    uri = post.get("uri") or ""
    if not uri:
        return None
    record = post.get("record") or {}
    author = post.get("author") or {}
    handle = author.get("handle") or "unknown"
    text_content = record.get("text") or ""
    posted_at = post.get("indexedAt") or record.get("createdAt") or datetime.now(timezone.utc).isoformat()
    fetched_at = datetime.now(timezone.utc).isoformat()

    media_url = _extract_first_image(post)
    media_path: Optional[str] = None

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM social_posts WHERE source = 'bluesky' AND external_id = :e"),
            {"e": uri},
        ).first()
        if existing is not None:
            return None
        result = conn.execute(
            text(
                "INSERT INTO social_posts (source, external_id, author_name, author_handle, "
                "  content, external_url, posted_at, fetched_at, media_path, featured, hidden) "
                "VALUES ('bluesky', :external_id, :author_name, :author_handle, :content, "
                "  :external_url, :posted_at, :fetched_at, :media_path, 0, :hidden)"
            ),
            {
                "external_id": uri,
                "author_name": author.get("displayName") or handle,
                "author_handle": f"@{handle}",
                "content": text_content[:2000],
                "external_url": _post_url(handle, uri),
                "posted_at": posted_at,
                "fetched_at": fetched_at,
                "media_path": None,
                "hidden": 1 if hidden else 0,
            },
        )
        new_id = result.lastrowid
        # Download image after insert so the path includes the row id
        if media_url:
            ext = ".jpg"
            if media_url.lower().endswith(".png"):
                ext = ".png"
            elif media_url.lower().endswith(".webp"):
                ext = ".webp"
            dest = config.SOCIAL_MEDIA_DIR / f"bluesky-{new_id}{ext}"
            saved = _download_image(media_url, dest)
            if saved is not None:
                rel = f"/media-social/{saved.name}"
                conn.execute(
                    text("UPDATE social_posts SET media_path = :p WHERE id = :id"),
                    {"p": rel, "id": new_id},
                )
                media_path = rel  # noqa: F841 — kept for debugging
    return new_id


def run() -> dict:
    """One scrape cycle. Returns a summary dict; never raises."""
    _file_logger()
    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    auto_publish = config.SCRAPER_AUTO_PUBLISH
    hidden = not auto_publish
    try:
        with httpx.Client(
            timeout=10.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            resp = client.get(SEARCH_URL, params={"q": QUERY, "limit": PAGE_LIMIT})
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        posts = body.get("posts") or []
        for post in posts:
            try:
                new_id = _insert_post(post, hidden=hidden)
            except Exception as exc:  # noqa: BLE001 — keep going on per-post errors
                logger.warning("insert failed for %s: %s", post.get("uri"), exc)
                continue
            if new_id is not None:
                inserted += 1
                if not hidden:
                    try:
                        notify_bot(
                            "new_social",
                            {
                                "id": new_id,
                                "source": "bluesky",
                                "author": (post.get("author") or {}).get("displayName")
                                or (post.get("author") or {}).get("handle"),
                                "content": ((post.get("record") or {}).get("text") or "")[:280],
                                "external_url": _post_url(
                                    (post.get("author") or {}).get("handle") or "unknown",
                                    post.get("uri") or "",
                                ),
                            },
                        )
                        notified += 1
                    except Exception as exc:  # noqa: BLE001 — bot is best-effort
                        logger.warning("notify_bot failed: %s", exc)
        state.record_success(inserted=inserted)
        logger.info(
            "bluesky scrape OK fetched=%d inserted=%d notified=%d hidden=%s",
            len(posts),
            inserted,
            notified,
            hidden,
        )
        return {
            "ok": True,
            "fetched": len(posts),
            "inserted": inserted,
            "notified": notified,
            "hidden": hidden,
        }
    except Exception as exc:  # noqa: BLE001 — last line of defense
        state.record_failure(str(exc))
        logger.exception("bluesky scrape failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NMS10 Bluesky scraper")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()
    init_db()
    summary = run()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(summary)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_cli())

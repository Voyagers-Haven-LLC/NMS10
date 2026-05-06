"""Bluesky #NMS10 scraper.

Polls the public AT Protocol search endpoint, dedupes against
social_posts(source='bluesky', external_id=at_uri), and inserts new rows.
Embedded images are downloaded via the shared download_media helper.

Design notes
------------
* No auth — `app.bsky.feed.searchPosts` is public.
* External id = the at:// URI which is globally unique and stable.
* hidden flag = inverse of NMS10_SCRAPER_AUTO_PUBLISH (default: auto-publish on).
* On 3+ consecutive failures the scheduler reschedules to a slower interval.

Run modes
---------
* `python -m app.scrapers.bluesky --once` does one synchronous poll and exits.
  Used for verification and ad-hoc backfill.
* When the FastAPI app is up, APScheduler calls `run()` on a 5-minute interval.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import scraper_status
from ..db import init_db
from . import _base

NAME = "bluesky"
SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
QUERY = "#NMS10"
PAGE_LIMIT = 50
USER_AGENT = "nms10-bot/0.1 (+https://github.com/Parker1920/nms10-site)"
ENV_VARS: tuple[str, ...] = ()  # No credentials needed — public API

logger = logging.getLogger("nms10.scraper.bluesky")


def _post_url(handle: str, uri: str) -> str:
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def _extract_first_image(post: dict) -> Optional[str]:
    """Bluesky embeds: images, external (link card), recordWithMedia.
    Return the first usable image URL or None."""
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


def _process_post(post: dict, hidden: bool) -> Optional[int]:
    uri = post.get("uri") or ""
    if not uri:
        return None
    record = post.get("record") or {}
    author = post.get("author") or {}
    handle = author.get("handle") or "unknown"
    text_content = record.get("text") or ""
    posted_at = (
        post.get("indexedAt")
        or record.get("createdAt")
        or datetime.now(timezone.utc).isoformat()
    )

    # Relevance check — Bluesky's search is hashtag-aware so strict mode is fine.
    if not _base.text_matches_nms10(text_content, mode="strict"):
        return None

    new_id = _base.insert_post(
        source="bluesky",
        external_id=uri,
        author_name=author.get("displayName") or handle,
        author_handle=f"@{handle}",
        content=text_content,
        external_url=_post_url(handle, uri),
        posted_at=posted_at,
        hidden=hidden,
    )
    if new_id is None:
        return None

    # Download media after insert so the filename can include the row id
    media_url = _extract_first_image(post)
    if media_url:
        media_path = _base.download_media(media_url, NAME, str(new_id), logger)
        if media_path:
            _base.attach_media(new_id, media_path)
    return new_id


def run() -> dict:
    """One scrape cycle. Returns a summary dict; never raises."""
    _base.attach_file_logger(logger)
    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    hidden = not _base.auto_publish()
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
                new_id = _process_post(post, hidden=hidden)
            except Exception as exc:  # noqa: BLE001 — keep going on per-post errors
                logger.warning("insert failed for %s: %s", post.get("uri"), exc)
                continue
            if new_id is not None:
                inserted += 1
                if not hidden:
                    if _base.fire_new_social_notification(
                        post_id=new_id,
                        source="bluesky",
                        author=(post.get("author") or {}).get("displayName")
                        or (post.get("author") or {}).get("handle"),
                        content=((post.get("record") or {}).get("text") or ""),
                        external_url=_post_url(
                            (post.get("author") or {}).get("handle") or "unknown",
                            post.get("uri") or "",
                        ),
                        logger=logger,
                    ):
                        notified += 1
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

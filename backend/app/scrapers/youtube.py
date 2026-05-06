"""YouTube #NMS10 scraper.

Hits the YouTube Data API v3 search endpoint, dedupes against
social_posts(source='youtube', external_id=videoId), and inserts new rows.
Thumbnails get downloaded via the shared helper.

Auth
----
A single API key in the YOUTUBE_API_KEY env var. Get one from
https://console.cloud.google.com/ → enable YouTube Data API v3 → Credentials.
Free quota is 10,000 units/day; a search costs 100 units, a videos.list call
costs 1 unit. At a 30-min schedule that's 48 searches/day = 4800 units, well
under quota.

Run modes
---------
* `python -m app.scrapers.youtube --once`
* APScheduler every 30 min when the FastAPI app is up.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

import httpx

from .. import scraper_status
from ..db import init_db
from . import _base

NAME = "youtube"
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
# Pair the hashtag with the game name so unrelated #10 episodes / NBA 2K
# MyTeam content doesn't match. YouTube's search ignores the # but the
# combined query nudges relevance up. The client-side filter
# (text_matches_nms10) is the real safety net.
QUERY = '#NMS10 "No Man\'s Sky"'
PAGE_LIMIT = 25
ENV_VARS = ("YOUTUBE_API_KEY",)

logger = logging.getLogger("nms10.scraper.youtube")


def _process_video(item: dict, hidden: bool) -> Optional[int]:
    video_id = (item.get("id") or {}).get("videoId") if isinstance(item.get("id"), dict) else item.get("id")
    if not video_id:
        return None
    snippet = item.get("snippet") or {}
    channel_title = snippet.get("channelTitle") or "unknown"
    title = snippet.get("title") or ""
    description = snippet.get("description") or ""

    # Relevance gate — YouTube search returns lots of #10/NBA 2K junk that
    # the medium-mode filter rejects.
    if not _base.text_matches_nms10(f"{title} {description}", mode="medium"):
        return None

    # Display content = title (short, readable). Description goes unused on
    # the public card but it informed the filter above.
    new_id = _base.insert_post(
        source="youtube",
        external_id=video_id,
        author_name=channel_title,
        author_handle=f"@{channel_title}",
        content=title,
        external_url=f"https://www.youtube.com/watch?v={video_id}",
        posted_at=snippet.get("publishedAt"),
        hidden=hidden,
    )
    if new_id is None:
        return None

    thumbs = snippet.get("thumbnails") or {}
    # Prefer 'high' (480x360), fall back to 'medium', then 'default'
    thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    if thumb:
        media_path = _base.download_media(thumb, NAME, str(new_id), logger)
        if media_path:
            _base.attach_media(new_id, media_path)
    return new_id


def run() -> dict:
    """One scrape cycle. Returns a summary dict; never raises."""
    _base.attach_file_logger(logger)
    missing = _base.has_stub_credentials(ENV_VARS)
    if missing is not None:
        return _base.mark_stub_skip(NAME, missing, logger)

    import os  # local — only resolved when we have creds
    api_key = os.environ["YOUTUBE_API_KEY"].strip()

    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    hidden = not _base.auto_publish()

    try:
        with httpx.Client(
            timeout=10.0,
            headers={"User-Agent": _base.USER_AGENT_DEFAULT, "Accept": "application/json"},
        ) as client:
            params = {
                "part": "snippet",
                "q": QUERY,
                "type": "video",
                "order": "date",
                "maxResults": PAGE_LIMIT,
                "key": api_key,
            }
            resp = client.get(SEARCH_URL, params=params)
        # YouTube returns 400 for "API key not valid" (most common bad-key
        # case), 403 for quota / disabled, 401 for unauthenticated. Treat
        # any of these + a key-related body as auth failure.
        if resp.status_code in (400, 401, 403):
            body_lower = resp.text[:500].lower()
            if (
                "api key not valid" in body_lower
                or "api key" in body_lower
                or "keyinvalid" in body_lower
                or "quota" in body_lower
                or resp.status_code in (401, 403)
            ):
                _base.mark_auth_failure(NAME, f"HTTP {resp.status_code}: {resp.text[:200]}", logger)
                return {"ok": False, "error": f"auth failed: HTTP {resp.status_code}", "inserted": 0}
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        items = body.get("items") or []
        # If we'd previously been auth-failed, recover that state
        if state.auth_state == "auth-failed":
            state.set_auth_state("ok")

        for item in items:
            try:
                new_id = _process_video(item, hidden=hidden)
            except Exception as exc:  # noqa: BLE001
                logger.warning("insert failed for %s: %s", item.get("id"), exc)
                continue
            if new_id is not None:
                inserted += 1
                if not hidden:
                    if _base.fire_new_social_notification(
                        post_id=new_id,
                        source="youtube",
                        author=(item.get("snippet") or {}).get("channelTitle"),
                        content=(item.get("snippet") or {}).get("title") or "",
                        external_url=f"https://www.youtube.com/watch?v={(item.get('id') or {}).get('videoId') if isinstance(item.get('id'), dict) else item.get('id')}",
                        logger=logger,
                    ):
                        notified += 1
        state.record_success(inserted=inserted)
        logger.info(
            "youtube scrape OK fetched=%d inserted=%d notified=%d hidden=%s",
            len(items), inserted, notified, hidden,
        )
        return {
            "ok": True,
            "fetched": len(items),
            "inserted": inserted,
            "notified": notified,
            "hidden": hidden,
        }
    except Exception as exc:  # noqa: BLE001
        state.record_failure(str(exc))
        logger.exception("youtube scrape failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NMS10 YouTube scraper")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--json", action="store_true")
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

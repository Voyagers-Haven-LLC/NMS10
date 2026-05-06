"""Twitter / X #NMS10 scraper using Scweet 5.x.

Scweet drives a logged-in browser session via an auth_token cookie scraped
from a real account. Single burner account, low volume. No proxies.

Auth setup
----------
1. Log in to https://x.com from a clean browser profile.
2. DevTools → Application → Cookies → x.com → copy `auth_token` value.
3. Set TWITTER_AUTH_TOKEN env var to that string.

If/when the token expires (account banned, password reset, X invalidates
session), the scraper marks itself auth-failed in scraper_status and stops
trying until you provide a fresh token. **Do not auto-rotate** — you'll burn
the burner.

Failure modes
-------------
* Scweet raises AuthError → mark auth-failed, log loud, return.
* Network / parse errors → record_failure, scheduler may push to slow lane.
* X changes their internal API (which they do regularly) → we'll see RunFailed
  or similar and just record the failure. Update Scweet to a newer version.

Run modes
---------
* `python -m app.scrapers.twitter --once`
* APScheduler every 30 min when the FastAPI app is up.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Optional

from .. import scraper_status
from ..db import init_db
from . import _base

NAME = "twitter"
QUERY = "#NMS10"
PAGE_LIMIT = 50
ENV_VARS = ("TWITTER_AUTH_TOKEN",)

logger = logging.getLogger("nms10.scraper.twitter")

_client: Any = None  # cached Scweet instance — building one is expensive


def _pick(d: dict, *keys: str, default=None):
    """Try several possible keys, return first non-None value."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return default


def _tweet_id(t: dict) -> Optional[str]:
    return _pick(t, "id", "tweet_id", "id_str", "rest_id")


def _tweet_handle(t: dict) -> Optional[str]:
    user = t.get("user") if isinstance(t.get("user"), dict) else None
    if user:
        return _pick(user, "screen_name", "username", "handle")
    return _pick(t, "username", "screen_name", "user_screen_name")


def _tweet_name(t: dict) -> Optional[str]:
    user = t.get("user") if isinstance(t.get("user"), dict) else None
    if user:
        return _pick(user, "name", "display_name")
    return _pick(t, "user_name", "display_name", "name")


def _tweet_text(t: dict) -> str:
    return _pick(t, "full_text", "text", "content") or ""


def _tweet_created_at(t: dict) -> Optional[str]:
    return _pick(t, "created_at", "date", "timestamp", "datetime")


def _tweet_first_media_url(t: dict) -> Optional[str]:
    """Best-effort first-image extraction across possible Scweet shapes."""
    media = _pick(t, "media", "photos", "images", default=None)
    if not media:
        return None
    if isinstance(media, list) and media:
        item = media[0]
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return _pick(item, "media_url", "media_url_https", "url", "src")
    return None


def _build_url(handle: Optional[str], tid: Optional[str]) -> Optional[str]:
    if not tid:
        return None
    if handle:
        return f"https://twitter.com/{handle.lstrip('@')}/status/{tid}"
    return f"https://twitter.com/i/web/status/{tid}"


def _get_client():
    """Build (and cache) a Scweet client. Re-raised AuthError signals
    creds are dead; the scheduler caller catches and records auth-failed."""
    global _client
    if _client is not None:
        return _client
    from Scweet import Scweet  # type: ignore

    token = os.environ["TWITTER_AUTH_TOKEN"].strip()
    _client = Scweet(
        auth_token=token,
        manifest_scrape_on_init=True,
        db_path=str(_base_db_path()),
    )
    return _client


def _base_db_path():
    """Keep Scweet's internal state in /data so it persists across restarts."""
    from .. import config
    p = config.DATA_DIR / ".scweet-state.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _process_tweet(tweet: dict, hidden: bool) -> Optional[int]:
    tid = _tweet_id(tweet)
    if not tid:
        return None
    handle = _tweet_handle(tweet)
    name = _tweet_name(tweet) or handle or "unknown"
    text_content = _tweet_text(tweet)
    created_at = _tweet_created_at(tweet)
    url = _build_url(handle, str(tid))

    if not _base.text_matches_nms10(text_content, mode="strict"):
        return None

    new_id = _base.insert_post(
        source="twitter",
        external_id=str(tid),
        author_name=name,
        author_handle=f"@{handle}" if handle else None,
        content=text_content,
        external_url=url,
        posted_at=str(created_at) if created_at else None,
        hidden=hidden,
    )
    if new_id is None:
        return None

    media_url = _tweet_first_media_url(tweet)
    if media_url:
        media_path = _base.download_media(media_url, NAME, str(new_id), logger)
        if media_path:
            _base.attach_media(new_id, media_path)
    return new_id


def run() -> dict:
    _base.attach_file_logger(logger)
    missing = _base.has_stub_credentials(ENV_VARS)
    if missing is not None:
        return _base.mark_stub_skip(NAME, missing, logger)

    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    hidden = not _base.auto_publish()

    # Lazy-import so module-level import doesn't fail when Scweet's deps act up
    try:
        from Scweet import AuthError  # type: ignore
    except ImportError:
        AuthError = Exception  # fallback: any exception triggers the same path

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001 — could be AuthError or init issue
        if isinstance(exc, AuthError) or "auth" in str(exc).lower():
            _base.mark_auth_failure(
                NAME,
                f"Twitter burner account token expired or banned. "
                f"Update TWITTER_AUTH_TOKEN env var. ({exc})",
                logger,
            )
            return {"ok": False, "error": str(exc), "inserted": 0}
        state.record_failure(str(exc))
        logger.exception("twitter init failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": 0}

    try:
        tweets = client.search(QUERY, limit=PAGE_LIMIT) or []
        if tweets and isinstance(tweets[0], dict):
            logger.info("twitter first tweet keys: %s", sorted(tweets[0].keys()))
        if state.auth_state == "auth-failed":
            state.set_auth_state("ok")
        for tweet in tweets:
            if not isinstance(tweet, dict):
                continue
            try:
                new_id = _process_tweet(tweet, hidden=hidden)
            except Exception as exc:  # noqa: BLE001
                logger.warning("twitter insert failed for %s: %s", _tweet_id(tweet), exc)
                continue
            if new_id is not None:
                inserted += 1
                if not hidden:
                    if _base.fire_new_social_notification(
                        post_id=new_id,
                        source="twitter",
                        author=_tweet_name(tweet) or _tweet_handle(tweet),
                        content=_tweet_text(tweet),
                        external_url=_build_url(_tweet_handle(tweet), str(_tweet_id(tweet))),
                        logger=logger,
                    ):
                        notified += 1
        state.record_success(inserted=inserted)
        logger.info(
            "twitter scrape OK fetched=%d inserted=%d notified=%d hidden=%s",
            len(tweets), inserted, notified, hidden,
        )
        return {
            "ok": True,
            "fetched": len(tweets),
            "inserted": inserted,
            "notified": notified,
            "hidden": hidden,
        }
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, AuthError) or "auth" in str(exc).lower() or "401" in str(exc):
            _base.mark_auth_failure(
                NAME,
                f"Twitter burner account token expired or banned. "
                f"Update TWITTER_AUTH_TOKEN env var. ({exc})",
                logger,
            )
            return {"ok": False, "error": str(exc), "inserted": inserted}
        state.record_failure(str(exc))
        logger.exception("twitter scrape failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NMS10 Twitter scraper")
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

"""Reddit #NMS10 scraper.

Reddit OAuth client_credentials flow. Searches r/NoMansSkyTheGame and
r/NMSCoordinateExchange for "#NMS10" posts. The token gets re-fetched on a
401 (cheap, the API permits this) so we don't have to manage a separate
refresh schedule.

Auth setup
----------
Register a "script" app at https://www.reddit.com/prefs/apps. You'll get a
client_id (under the app name) and a client_secret. Set:

  REDDIT_CLIENT_ID
  REDDIT_CLIENT_SECRET
  REDDIT_USER_AGENT (Reddit *requires* a unique, identifiable UA)

Run modes
---------
* `python -m app.scrapers.reddit --once`
* APScheduler every 10 min when the FastAPI app is up.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import scraper_status
from ..db import init_db
from . import _base

NAME = "reddit"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/r/{sub}/search"
SUBREDDITS = ("NoMansSkyTheGame", "NMSCoordinateExchange")
QUERY = "#NMS10"
PAGE_LIMIT = 50
DEFAULT_USER_AGENT = "nms10-aggregator/1.0 (by /u/Parker1920)"
ENV_VARS = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")

logger = logging.getLogger("nms10.scraper.reddit")

_token_cache: dict[str, object] = {"value": None, "expires_at": 0.0}


def _user_agent() -> str:
    return os.environ.get("REDDIT_USER_AGENT", "").strip() or DEFAULT_USER_AGENT


def _fetch_token() -> str:
    """Get an OAuth access token via client_credentials. Cached for ~50 min."""
    now = datetime.now(timezone.utc).timestamp()
    cached = _token_cache.get("value")
    expires_at = float(_token_cache.get("expires_at") or 0.0)
    if cached and now < expires_at - 60:
        return str(cached)
    cid = os.environ["REDDIT_CLIENT_ID"].strip()
    secret = os.environ["REDDIT_CLIENT_SECRET"].strip()
    with httpx.Client(timeout=10.0, headers={"User-Agent": _user_agent()}) as client:
        resp = client.post(
            TOKEN_URL,
            auth=(cid, secret),
            data={"grant_type": "client_credentials"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"reddit token HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"reddit token response missing access_token: {data!r}")
    _token_cache["value"] = token
    _token_cache["expires_at"] = now + float(data.get("expires_in") or 3600)
    return str(token)


def _post_url(permalink: str) -> str:
    if not permalink:
        return ""
    if permalink.startswith("http"):
        return permalink
    return f"https://reddit.com{permalink}"


def _epoch_to_iso(value) -> Optional[str]:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _process_post(post: dict, hidden: bool) -> Optional[int]:
    name = post.get("name") or ""  # e.g. "t3_abc123"
    if not name:
        return None
    title = post.get("title") or ""
    selftext = post.get("selftext") or ""
    content_combined = title if not selftext else f"{title}\n\n{selftext}"

    new_id = _base.insert_post(
        source="reddit",
        external_id=name,
        author_name=f"u/{post.get('author') or 'unknown'}",
        author_handle=f"r/{post.get('subreddit') or ''}",
        content=content_combined,
        external_url=_post_url(post.get("permalink") or ""),
        posted_at=_epoch_to_iso(post.get("created_utc")),
        hidden=hidden,
    )
    if new_id is None:
        return None

    # Reddit thumbnail can be: a real URL, "self", "default", "nsfw", "spoiler", or ""
    thumb = post.get("thumbnail") or ""
    if thumb.startswith("http"):
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

    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    fetched = 0
    hidden = not _base.auto_publish()

    try:
        token = _fetch_token()
    except Exception as exc:  # noqa: BLE001
        _base.mark_auth_failure(NAME, str(exc), logger)
        return {"ok": False, "error": f"token fetch failed: {exc}", "inserted": 0}

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            for sub in SUBREDDITS:
                params = {
                    "q": QUERY,
                    "sort": "new",
                    "limit": PAGE_LIMIT,
                    "restrict_sr": "true",
                }
                resp = client.get(SEARCH_URL.format(sub=sub), params=params)
                if resp.status_code == 401:
                    _base.mark_auth_failure(NAME, f"HTTP 401 from r/{sub}", logger)
                    return {"ok": False, "error": "401 unauthorized", "inserted": inserted}
                if resp.status_code != 200:
                    logger.warning("r/%s search HTTP %s: %s", sub, resp.status_code, resp.text[:200])
                    continue
                body = resp.json()
                children = (body.get("data") or {}).get("children") or []
                fetched += len(children)
                for child in children:
                    post = child.get("data") or {}
                    try:
                        new_id = _process_post(post, hidden=hidden)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("insert failed for %s: %s", post.get("name"), exc)
                        continue
                    if new_id is not None:
                        inserted += 1
                        if not hidden:
                            if _base.fire_new_social_notification(
                                post_id=new_id,
                                source="reddit",
                                author=f"u/{post.get('author') or 'unknown'}",
                                content=post.get("title") or "",
                                external_url=_post_url(post.get("permalink") or ""),
                                logger=logger,
                            ):
                                notified += 1
        if state.auth_state == "auth-failed":
            state.set_auth_state("ok")
        state.record_success(inserted=inserted)
        logger.info(
            "reddit scrape OK fetched=%d inserted=%d notified=%d hidden=%s",
            fetched, inserted, notified, hidden,
        )
        return {
            "ok": True,
            "fetched": fetched,
            "inserted": inserted,
            "notified": notified,
            "hidden": hidden,
        }
    except Exception as exc:  # noqa: BLE001
        state.record_failure(str(exc))
        logger.exception("reddit scrape failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NMS10 Reddit scraper")
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

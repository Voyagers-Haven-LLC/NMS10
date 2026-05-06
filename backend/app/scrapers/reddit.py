"""Reddit #NMS10 scraper.

Two operational modes, picked at run time:

1. **OAuth** (preferred). Uses client_credentials against oauth.reddit.com.
   Higher rate limit (~600 req/min). Activated when both REDDIT_CLIENT_ID
   and REDDIT_CLIENT_SECRET are set to non-STUB values.

2. **Unauthenticated public JSON** (fallback). Hits
   https://www.reddit.com/r/<sub>/search.json directly. No app registration
   required. Rate-limited to ~60 req/min unauth, which is fine for our
   10-min schedule (2 subs per cycle = 12 req/hr). Activated when either
   OAuth env var is missing or set to STUB.

Reddit *requires* a unique, identifiable User-Agent in either mode. Set
REDDIT_USER_AGENT to something like "nms10-aggregator/1.0 by /u/<username>".

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
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import scraper_status
from ..db import init_db
from . import _base

NAME = "reddit"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_SEARCH_URL = "https://oauth.reddit.com/r/{sub}/search"
# old.reddit.com hosts the same search endpoint as www but routes through a
# separate stack that's much more lenient on unauthenticated read traffic.
PUBLIC_SEARCH_URL = "https://old.reddit.com/r/{sub}/search.json"
SUBREDDITS = ("NoMansSkyTheGame", "NMSCoordinateExchange")
# Reddit doesn't treat # as a hashtag and the NMS subs largely use natural
# language for the anniversary, so we search several phrases and union the
# results. Dedupe is at the (source, external_id) level via insert_post().
# One query, two subs = two requests per cycle. Reddit's unauth bot detection
# is aggressive; the more requests we send the more likely they 403 us.
# When OAuth is set up, you can safely add more queries here — OAuth gets
# 600 req/min and is much harder to trip.
QUERIES = ("NMS10",)
PAGE_LIMIT = 25
REQUEST_DELAY_SECONDS = 4.0
DEFAULT_USER_AGENT = "nms10-aggregator/1.0 (by /u/Parker1920)"
OAUTH_ENV_VARS = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")

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

    if not _base.text_matches_nms10(content_combined, mode="medium"):
        return None

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
    """One scrape cycle. Returns a summary dict; never raises.

    Picks OAuth when both credentials env vars are set; otherwise hits the
    public JSON endpoint unauthenticated."""
    _base.attach_file_logger(logger)
    use_oauth = _base.has_stub_credentials(OAUTH_ENV_VARS) is None

    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    fetched = 0
    hidden = not _base.auto_publish()

    headers: dict[str, str] = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }

    if use_oauth:
        try:
            token = _fetch_token()
        except Exception as exc:  # noqa: BLE001
            _base.mark_auth_failure(NAME, str(exc), logger)
            return {"ok": False, "error": f"token fetch failed: {exc}", "inserted": 0}
        headers["Authorization"] = f"Bearer {token}"
        search_url_template = OAUTH_SEARCH_URL
    else:
        # Unauthenticated mode — hit www.reddit.com/.../search.json directly.
        # Don't use mark_stub_skip; this isn't a skip, we're actually scraping.
        # If state was previously stub-credentials, leave it that way until the
        # request actually succeeds (then we flip to ok).
        search_url_template = PUBLIC_SEARCH_URL
        logger.info("reddit running in unauthenticated mode (60 req/min limit)")

    seen_in_run: set[str] = set()
    request_count = 0
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            for sub in SUBREDDITS:
                for query in QUERIES:
                    if request_count > 0:
                        time.sleep(REQUEST_DELAY_SECONDS)
                    request_count += 1
                    params = {
                        "q": query,
                        "sort": "new",
                        "limit": PAGE_LIMIT,
                        "restrict_sr": "true",
                    }
                    resp = client.get(search_url_template.format(sub=sub), params=params)
                    if resp.status_code == 401:
                        _base.mark_auth_failure(NAME, f"HTTP 401 from r/{sub}", logger)
                        return {"ok": False, "error": "401 unauthorized", "inserted": inserted}
                    if resp.status_code == 429 or (resp.status_code == 403 and not use_oauth):
                        # 403 in unauth mode usually means rate-limit / bot detection.
                        # In OAuth mode 403 is a real permission error and should
                        # fall through to the generic warning branch below.
                        state.record_failure(
                            f"r/{sub} q={query!r} rate-limited (HTTP {resp.status_code}); back off"
                        )
                        logger.warning(
                            "reddit r/%s q=%s rate-limited (HTTP %s); sleeping until next cycle",
                            sub, query, resp.status_code,
                        )
                        return {"ok": False, "error": f"rate limited (HTTP {resp.status_code})", "inserted": inserted}
                    if resp.status_code != 200:
                        logger.warning("r/%s q=%s HTTP %s: %s", sub, query, resp.status_code, resp.text[:200])
                        continue
                    body = resp.json()
                    children = (body.get("data") or {}).get("children") or []
                    fetched += len(children)
                    for child in children:
                        post = child.get("data") or {}
                        name = post.get("name") or ""
                        # Dedupe within a single run so 4 queries × 2 subs don't
                        # try to insert the same post 8 times.
                        if name in seen_in_run:
                            continue
                        seen_in_run.add(name)
                        try:
                            new_id = _process_post(post, hidden=hidden)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("insert failed for %s: %s", name, exc)
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
        # Successful run — recover state from any prior degraded state.
        if state.auth_state in ("auth-failed", "stub-credentials"):
            state.set_auth_state("ok")
        state.record_success(inserted=inserted)
        mode = "oauth" if use_oauth else "unauth"
        logger.info(
            "reddit scrape OK mode=%s fetched=%d inserted=%d notified=%d hidden=%s",
            mode, fetched, inserted, notified, hidden,
        )
        return {
            "ok": True,
            "mode": mode,
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

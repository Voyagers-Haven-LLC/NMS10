"""Instagram #nms10 scraper using instagrapi.

instagrapi drives Instagram's *private* API via a logged-in session. The
session blob is persisted to /data/.instagram-session.json so we don't
re-login every cycle — instagrapi docs warn that re-authing in a tight
loop is the fastest way to get the burner banned.

Auth setup
----------
1. Create a fresh Instagram account on a personal device, **not the Pi**.
2. Use it normally for ~2 weeks before pointing this scraper at it.
3. Set:
     INSTAGRAM_USERNAME=...
     INSTAGRAM_PASSWORD=...
4. First run: the scraper logs in once and writes
   `/data/.instagram-session.json`. After that we relogin from the saved
   session, which is dramatically less suspicious to Instagram.

Failure modes
-------------
* `LoginRequired`, `ChallengeRequired`, `FeedbackRequired` →
  mark auth-failed and STOP. Do not auto-retry. Per instagrapi docs,
  retrying after a challenge can escalate the ban.
* Network or parse errors → record_failure normally.

Run modes
---------
* `python -m app.scrapers.instagram --once`
* APScheduler every 30 min when the FastAPI app is up.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .. import config, scraper_status
from ..db import init_db
from . import _base

NAME = "instagram"
HASHTAG = "nms10"
PAGE_LIMIT = 25
ENV_VARS = ("INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD")
SESSION_PATH = config.DATA_DIR / ".instagram-session.json"

logger = logging.getLogger("nms10.scraper.instagram")

_client: Any = None  # cache the logged-in client across runs


def _safe_str(v) -> Optional[str]:
    if v is None:
        return None
    return str(v)


def _coerce_dt(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _login_or_load() -> Any:
    """Reuse a saved session if present, fall back to fresh login."""
    from instagrapi import Client  # type: ignore

    username = os.environ["INSTAGRAM_USERNAME"].strip()
    password = os.environ["INSTAGRAM_PASSWORD"].strip()

    cl = Client()
    cl.delay_range = [1, 3]  # randomize request delay slightly
    if SESSION_PATH.exists():
        try:
            cl.load_settings(str(SESSION_PATH))
            cl.login(username, password)  # ratifies session
            cl.get_timeline_feed()  # cheap ping to confirm session validity
            logger.info("instagram session reused from %s", SESSION_PATH)
            return cl
        except Exception as exc:  # noqa: BLE001 — fall through to fresh login
            logger.warning("instagram saved session unusable (%s) — re-logging in", exc)
            try:
                SESSION_PATH.unlink()
            except OSError:
                pass

    cl.login(username, password)
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(str(SESSION_PATH))
    logger.info("instagram fresh login complete; saved session to %s", SESSION_PATH)
    return cl


def _process_media(media, hidden: bool) -> Optional[int]:
    pk = getattr(media, "pk", None) or getattr(media, "id", None)
    if pk is None:
        return None
    pk = str(pk)
    code = getattr(media, "code", None) or pk
    user = getattr(media, "user", None)
    full_name = getattr(user, "full_name", None) if user else None
    username = getattr(user, "username", None) if user else None
    caption = getattr(media, "caption_text", None) or "(no caption)"
    posted_at = _coerce_dt(getattr(media, "taken_at", None))
    thumb = getattr(media, "thumbnail_url", None)
    if thumb is not None:
        thumb = _safe_str(thumb)

    if not _base.text_matches_nms10(caption, mode="strict"):
        return None

    new_id = _base.insert_post(
        source="instagram",
        external_id=pk,
        author_name=full_name or username or "unknown",
        author_handle=f"@{username}" if username else None,
        content=caption,
        external_url=f"https://instagram.com/p/{code}",
        posted_at=posted_at,
        hidden=hidden,
    )
    if new_id is None:
        return None

    if thumb:
        media_path = _base.download_media(thumb, NAME, str(new_id), logger)
        if media_path:
            _base.attach_media(new_id, media_path)
    return new_id


def _is_auth_error(exc: Exception) -> bool:
    name = type(exc).__name__
    return name in {"LoginRequired", "ChallengeRequired", "FeedbackRequired"} or "login" in name.lower()


def run() -> dict:
    _base.attach_file_logger(logger)
    missing = _base.has_stub_credentials(ENV_VARS)
    if missing is not None:
        return _base.mark_stub_skip(NAME, missing, logger)

    state = scraper_status.get(NAME)
    inserted = 0
    notified = 0
    hidden = not _base.auto_publish()

    global _client
    try:
        if _client is None:
            _client = _login_or_load()
    except Exception as exc:  # noqa: BLE001
        if _is_auth_error(exc):
            _base.mark_auth_failure(
                NAME,
                f"Instagram login blocked ({type(exc).__name__}): {exc}. "
                f"Do NOT retry — log in manually from a clean device first.",
                logger,
            )
            _client = None
            return {"ok": False, "error": str(exc), "inserted": 0}
        state.record_failure(str(exc))
        logger.exception("instagram login failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": 0}

    try:
        media_list = _client.hashtag_medias_recent(HASHTAG, amount=PAGE_LIMIT) or []
        if state.auth_state == "auth-failed":
            state.set_auth_state("ok")
        for media in media_list:
            try:
                new_id = _process_media(media, hidden=hidden)
            except Exception as exc:  # noqa: BLE001
                logger.warning("instagram insert failed for %s: %s", getattr(media, "pk", "?"), exc)
                continue
            if new_id is not None:
                inserted += 1
                if not hidden:
                    user = getattr(media, "user", None)
                    if _base.fire_new_social_notification(
                        post_id=new_id,
                        source="instagram",
                        author=getattr(user, "full_name", None) or getattr(user, "username", None) if user else None,
                        content=getattr(media, "caption_text", None) or "",
                        external_url=f"https://instagram.com/p/{getattr(media, 'code', '')}",
                        logger=logger,
                    ):
                        notified += 1
        state.record_success(inserted=inserted)
        logger.info(
            "instagram scrape OK fetched=%d inserted=%d notified=%d hidden=%s",
            len(media_list), inserted, notified, hidden,
        )
        return {
            "ok": True,
            "fetched": len(media_list),
            "inserted": inserted,
            "notified": notified,
            "hidden": hidden,
        }
    except Exception as exc:  # noqa: BLE001
        if _is_auth_error(exc):
            _base.mark_auth_failure(
                NAME,
                f"Instagram session blocked mid-scrape ({type(exc).__name__}): {exc}. "
                f"Do NOT retry until you've manually logged in from a clean device.",
                logger,
            )
            _client = None  # force fresh login attempt next cycle (manual)
            return {"ok": False, "error": str(exc), "inserted": inserted}
        state.record_failure(str(exc))
        logger.exception("instagram scrape failed: %s", exc)
        return {"ok": False, "error": str(exc), "inserted": inserted}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NMS10 Instagram scraper")
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

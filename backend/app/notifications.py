"""Internal bot webhook helper.

Backend code calls notify_bot(type, payload) to inform the Discord bot
about a new submission, an approval, or a freshly-scraped social post.
The bot listens on http://127.0.0.1:9000/notify (loopback only). If the
bot is unreachable the call logs a warning and returns — submissions
must NEVER fail because the bot is down.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from . import config

logger = logging.getLogger("nms10.notify")

NOTIFY_TIMEOUT = 2.0  # seconds


def _post_sync(url: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "nms10-backend/0.1"},
    )
    try:
        with urlopen(req, timeout=NOTIFY_TIMEOUT) as resp:
            resp.read()
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("bot webhook unreachable (%s): %s", config.BOT_WEBHOOK_URL, exc)


def notify_bot(notification_type: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget POST to the bot's webhook. Runs in a background
    thread so callers (FastAPI handlers) aren't blocked on a missing bot."""
    body = {"type": notification_type, "payload": payload}
    url = config.BOT_WEBHOOK_URL
    if not url:
        return
    t = threading.Thread(target=_post_sync, args=(url, body), daemon=True)
    t.start()


async def notify_bot_async(notification_type: str, payload: dict[str, Any]) -> None:
    """Async variant for use inside the scrapers, which run on the event loop.
    Uses asyncio.to_thread so the same urllib path works without an extra dep."""
    await asyncio.to_thread(notify_bot, notification_type, payload)

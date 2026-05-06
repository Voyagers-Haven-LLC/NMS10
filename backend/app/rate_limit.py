"""Rate-limit setup for public submission endpoints.

Built on slowapi (in-memory, per-process). Public IPs are limited to
NMS10_SUBMISSION_RATE_LIMIT (default "5/hour") on POST /api/submissions/*.

The Discord bot is treated as a trusted submitter and bypasses the limit
by sending the `X-NMS10-Bot-Secret` header with a value matching
BOT_INTERNAL_SECRET. The secret is auto-generated on first boot and
persisted to data/.bot-internal-secret. The bot reads the same value
from its env (or the same file when both run on the same host).

Implementation note: slowapi can't return None from key_func, so for bot
requests we return a unique-per-call key — that means each bot request
lives in its own bucket and never trips the limit. Functionally
equivalent to "no limit" for the bot.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import config

BOT_HEADER = "X-NMS10-Bot-Secret"


def _is_bot_request(request: Optional[Request]) -> bool:
    if request is None:
        return False
    secret = request.headers.get(BOT_HEADER)
    return bool(secret) and secret == config.BOT_INTERNAL_SECRET


def submission_key_func(request: Request) -> str:
    """slowapi key extractor: per-IP for the public, never-collides for
    the bot (effectively bypassed)."""
    if _is_bot_request(request):
        # Unique per call — no two bot requests ever hash to the same bucket.
        return f"bot-bypass:{time.time_ns()}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=submission_key_func,
    default_limits=[],   # apply per-route only, never globally
    headers_enabled=False,  # don't inject X-RateLimit-* — slowapi requires
                            # routes to accept a Response param when this is on,
                            # and we'd rather keep the route signatures clean
)

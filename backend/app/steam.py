"""Steam concurrent player count refresher.

Owns the actual fetch + cache write. Scheduling is owned by `scheduling.py`,
which calls `refresh_now()` on a 60s interval. The /api/steam-count endpoint
reads the cached row, so the API is decoupled from Steam's uptime."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen
import json

from sqlalchemy import text

from . import config
from .db import engine

logger = logging.getLogger("nms10.steam")


def _fetch_count() -> int | None:
    url = (
        "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
        f"?appid={config.STEAM_APP_ID}"
    )
    if config.STEAM_API_KEY:
        url += f"&key={config.STEAM_API_KEY}"
    req = Request(url, headers={"User-Agent": "nms10-site/0.1"})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Steam fetch failed: %s", exc)
        return None
    response = data.get("response") or {}
    if response.get("result") != 1:
        logger.warning("Steam API returned non-success: %s", data)
        return None
    return response.get("player_count")


def _upsert(count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT id FROM steam_cache WHERE id = 1")).first()
        if existing is None:
            conn.execute(
                text("INSERT INTO steam_cache (id, player_count, fetched_at) VALUES (1, :c, :t)"),
                {"c": count, "t": now},
            )
        else:
            conn.execute(
                text("UPDATE steam_cache SET player_count = :c, fetched_at = :t WHERE id = 1"),
                {"c": count, "t": now},
            )


def refresh_now() -> None:
    """Synchronous fetch — used at startup and by the scheduled job."""
    count = _fetch_count()
    if count is None:
        return
    _upsert(count)

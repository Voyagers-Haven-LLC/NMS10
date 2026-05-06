"""Per-guild channel config loader.

Reads bot/config/servers.yaml. Each entry is a Discord guild and three
optional channel ids (submission/approval/scraper). On reload, returns
both the new mapping and a structured diff for ack messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import yaml

from . import app_config

logger = logging.getLogger("nms10.bot.server_config")


@dataclass
class GuildRoute:
    guild_id: str
    name: str
    submission_announce_channel: Optional[int]
    approval_announce_channel: Optional[int]
    scraper_announce_channel: Optional[int]


_state: dict[str, GuildRoute] = {}


def _coerce_channel(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def load() -> dict[str, GuildRoute]:
    global _state
    path = app_config.SERVERS_FILE
    if not path.exists() or not path.is_file():
        # Common gotcha: compose bind-mount of a non-existent host file
        # silently creates an empty DIRECTORY at the container path. We
        # treat that the same as "missing" — log clearly, don't crash.
        why = "missing" if not path.exists() else "is a directory (likely a Docker bind-mount of a non-existent host file)"
        logger.warning("server config %s at %s — running with empty routes", why, path)
        _state = {}
        return _state
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("server config unreadable at %s (%s) — running with empty routes", path, exc)
        _state = {}
        return _state
    new_state: dict[str, GuildRoute] = {}
    for entry in raw.get("servers", []) or []:
        gid = str(entry.get("guild_id", "")).strip()
        if not gid:
            continue
        new_state[gid] = GuildRoute(
            guild_id=gid,
            name=entry.get("name") or gid,
            submission_announce_channel=_coerce_channel(entry.get("submission_announce_channel")),
            approval_announce_channel=_coerce_channel(entry.get("approval_announce_channel")),
            scraper_announce_channel=_coerce_channel(entry.get("scraper_announce_channel")),
        )
    _state = new_state
    return _state


def all_routes() -> dict[str, GuildRoute]:
    return dict(_state)


def channels_for(notification_type: str) -> list[int]:
    """Return all channel ids subscribed to the given notification type
    across every configured guild."""
    field_map = {
        "submission": "submission_announce_channel",
        "approved": "approval_announce_channel",
        "new_social": "scraper_announce_channel",
    }
    field = field_map.get(notification_type)
    if field is None:
        return []
    out = []
    for route in _state.values():
        ch = getattr(route, field, None)
        if ch:
            out.append(ch)
    return out

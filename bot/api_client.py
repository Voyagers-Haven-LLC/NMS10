"""Async wrapper around the NMS10 backend API. Used by the bot's slash
commands. Errors raise BackendError with a user-presentable message."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from . import app_config

logger = logging.getLogger("nms10.bot.api")

TIMEOUT_SECONDS = 5.0


class BackendError(Exception):
    pass


async def _request(method: str, path: str, json: Optional[dict] = None) -> Any:
    url = f"{app_config.BACKEND_URL}{path}"
    headers: dict[str, str] = {}
    # Send the rate-limit bypass header on submission writes. The backend
    # reads it from data/.bot-internal-secret if NMS10_BOT_INTERNAL_SECRET
    # isn't explicitly set; in shared-host dev the bot picks up the same
    # value from its env. Without this, a busy bot would hit the public
    # 5/hr per-IP limit (since both processes run on the same host IP).
    if app_config.BOT_INTERNAL_SECRET:
        headers["X-NMS10-Bot-Secret"] = app_config.BOT_INTERNAL_SECRET
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.request(method, url, json=json, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("backend request failed: %s", exc)
        raise BackendError(f"Backend unreachable: {exc}") from exc
    if resp.status_code >= 400:
        detail = resp.text[:300]
        try:
            data = resp.json()
            if isinstance(data, dict) and "detail" in data:
                detail = data["detail"] if isinstance(data["detail"], str) else str(data["detail"])
        except Exception:  # noqa: BLE001
            pass
        raise BackendError(f"Backend {resp.status_code}: {detail}")
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


async def submit_base(payload: dict) -> dict:
    return await _request("POST", "/api/submissions/bases", payload)


async def submit_community(payload: dict) -> dict:
    return await _request("POST", "/api/submissions/communities", payload)


async def submit_meetup(payload: dict) -> dict:
    return await _request("POST", "/api/submissions/meetups", payload)


async def submit_social(payload: dict) -> dict:
    return await _request("POST", "/api/submissions/socials", payload)


async def list_bases() -> list[dict]:
    return await _request("GET", "/api/bases") or []


async def list_communities() -> list[dict]:
    return await _request("GET", "/api/communities") or []


async def list_meetups() -> list[dict]:
    return await _request("GET", "/api/meetups") or []


async def list_socials() -> list[dict]:
    return await _request("GET", "/api/socials") or []


async def steam_count() -> dict:
    return await _request("GET", "/api/steam-count") or {}


async def health() -> dict:
    return await _request("GET", "/api/health") or {}

"""Loopback webhook receiver for backend → bot notifications.

The backend POSTs to http://127.0.0.1:9000/notify with shape:
    {"type": "submission" | "approved" | "new_social", "payload": {...}}

We dispatch to a channel-broadcast coroutine which posts the right embed
into every configured channel for that notification type.

The server only binds 127.0.0.1 by default. In a Docker compose setup the
backend and bot share a network, and you can override the host via
NMS10_BOT_WEBHOOK_HOST=0.0.0.0 to listen on the container network — but
even then the port is not published outside the host."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from aiohttp import web

from . import app_config

logger = logging.getLogger("nms10.bot.webhook")

DispatchFn = Callable[[str, dict], Awaitable[None]]


def make_app(dispatch: DispatchFn) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def notify(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"error": "invalid json"}, status=400)
        notification_type = (body or {}).get("type")
        payload = (body or {}).get("payload") or {}
        if not notification_type:
            return web.json_response({"error": "missing type"}, status=400)
        logger.info("recv notify type=%s entity=%s id=%s",
                    notification_type, payload.get("entity") or payload.get("source"),
                    payload.get("id"))
        try:
            await dispatch(notification_type, payload)
        except Exception as exc:  # noqa: BLE001 — never crash the webhook
            logger.exception("dispatch failed: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_post("/notify", notify)
    return app


async def start(dispatch: DispatchFn) -> Optional[web.AppRunner]:
    app = make_app(dispatch)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, app_config.WEBHOOK_HOST, app_config.WEBHOOK_PORT)
    await site.start()
    logger.info("webhook listening on http://%s:%s", app_config.WEBHOOK_HOST, app_config.WEBHOOK_PORT)
    return runner

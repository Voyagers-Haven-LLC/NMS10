"""FastAPI entry point. Wires the SQLite schema, admin bootstrap, seed,
scheduler (Steam + Bluesky), static media mounts, CORS, and routers."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from . import auth, config, scheduling, seed, steam
from .db import init_db
from .rate_limit import limiter
from .routers import (
    admin as admin_router,
    bases as bases_router,
    communities as communities_router,
    health as health_router,
    meetups as meetups_router,
    socials as socials_router,
    steam as steam_router,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.warn_defaults()
    init_db()
    auth.ensure_admin_user()
    seed.run_seed()
    config.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    config.SOCIAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    config.SCRAPER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    steam.refresh_now()
    scheduling.start()
    try:
        yield
    finally:
        scheduling.shutdown()


app = FastAPI(title="NMS10 API", version="0.2.0", lifespan=lifespan)

# Rate-limit support (per-IP, applied per-route via @limiter.limit on
# the public submission endpoints). Bot bypasses via X-NMS10-Bot-Secret.
# We don't add SlowAPIMiddleware — decorators alone enforce the limit, and
# skipping the middleware means our custom 429 handler below isn't bypassed.
app.state.limiter = limiter


def _rate_limit_handler(request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Too many submissions from this IP. Limit: {exc.detail}. "
                "Try again later, or use the Discord bot's /submit-* commands."
            ),
        },
        headers={"Retry-After": "60"},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# Origins that may call the API directly. Note: in the production compose
# layout the frontend nginx proxies /api/* on the same hostname (nms10.online),
# so the browser sees same-origin and CORS isn't actually invoked. The
# allowlist below covers (a) local dev (Vite on 5173 hitting :8000 directly)
# and (b) defensive coverage if anyone hits the API from a tool / second host.
_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://nms10.online",
    "https://www.nms10.online",
]
# Allow extra origins via env var (comma-separated) without code changes —
# useful if you spin up a staging subdomain or test-from-phone scenario.
_extra = (os.environ.get("NMS10_EXTRA_CORS_ORIGINS", "") or "").strip()
if _extra:
    _cors_origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static media. StaticFiles checks the directories at mount time, so we make
# sure they exist before the app object is constructed.
config.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
config.SOCIAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(config.MEDIA_DIR)), name="media")
app.mount("/media-social", StaticFiles(directory=str(config.SOCIAL_MEDIA_DIR)), name="media-social")

# Routers
app.include_router(health_router.router, prefix="/api")
app.include_router(bases_router.router, prefix="/api")
app.include_router(communities_router.router, prefix="/api")
app.include_router(meetups_router.router, prefix="/api")
app.include_router(socials_router.router, prefix="/api")
app.include_router(steam_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")

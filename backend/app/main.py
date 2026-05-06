"""FastAPI entry point. Wires the SQLite schema, admin bootstrap, seed,
scheduler (Steam + Bluesky), static media mounts, CORS, and routers."""

from __future__ import annotations

import logging
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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

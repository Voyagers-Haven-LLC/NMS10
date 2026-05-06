"""Single APScheduler instance for the FastAPI process.

Owns:
- Steam concurrent count refresh (every 60s)
- Bluesky #NMS10 scrape (every 5 min, with backoff to 15 min after 3+ failures)

The scheduler is started in lifespan() and shut down on app exit. Each job
is registered with `max_instances=1, coalesce=True` so we don't pile up if
a poll runs slow."""

from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import config, scraper_status, steam
from .scrapers import bluesky

logger = logging.getLogger("nms10.scheduling")

_scheduler: Optional[AsyncIOScheduler] = None


def _bluesky_job() -> None:
    """Wrapper that picks the right interval based on scraper backoff state.
    APScheduler doesn't support "change interval after N failures" natively,
    so we re-register the job after each run if the backoff state changed."""
    state = scraper_status.get(bluesky.NAME)
    was_in_backoff = state.in_backoff
    bluesky.run()
    is_in_backoff = state.in_backoff
    if was_in_backoff != is_in_backoff and _scheduler is not None:
        seconds = config.BLUESKY_BACKOFF_SECONDS if is_in_backoff else config.BLUESKY_REFRESH_SECONDS
        try:
            _scheduler.reschedule_job(
                "bluesky_scrape", trigger="interval", seconds=seconds
            )
            logger.info("bluesky job rescheduled to %ss (backoff=%s)", seconds, is_in_backoff)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not reschedule bluesky job: %s", exc)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        steam.refresh_now,
        "interval",
        seconds=config.STEAM_REFRESH_SECONDS,
        id="steam_refresh",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _bluesky_job,
        "interval",
        seconds=config.BLUESKY_REFRESH_SECONDS,
        id="bluesky_scrape",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("scheduler started: steam=%ss, bluesky=%ss",
                config.STEAM_REFRESH_SECONDS, config.BLUESKY_REFRESH_SECONDS)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

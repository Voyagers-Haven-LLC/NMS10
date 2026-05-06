"""Single APScheduler instance for the FastAPI process.

Owns:
- Steam concurrent count refresh (every 60s)
- 5 social scrapers (Bluesky, YouTube, Reddit, Twitter, Instagram), each
  on its own interval. Each scraper checks its env vars at run-time; when
  credentials are STUB the run is a no-op that flips auth_state to
  'stub-credentials' but the job stays registered so /admin/scraper-status
  still lists it.

Backoff: if a scraper's status flips into in_backoff (3+ consecutive failures),
its job is rescheduled to a slower interval. When it recovers, it goes back
to the healthy cadence.
"""

from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import config, db, scraper_status, steam
from .scrapers import bluesky, instagram, reddit, twitter, youtube

logger = logging.getLogger("nms10.scheduling")

_scheduler: Optional[AsyncIOScheduler] = None


# (module, job_id, healthy_seconds, backoff_seconds)
_SCRAPER_REGISTRY = (
    (bluesky,   "bluesky_scrape",   config.BLUESKY_REFRESH_SECONDS, config.BLUESKY_BACKOFF_SECONDS),
    (youtube,   "youtube_scrape",   30 * 60,                         60 * 60),
    (reddit,    "reddit_scrape",    10 * 60,                         30 * 60),
    (twitter,   "twitter_scrape",   30 * 60,                         60 * 60),
    (instagram, "instagram_scrape", 30 * 60,                         60 * 60),
)


def _wrap(module, job_id: str, healthy: int, backoff: int):
    """Build a job function that handles backoff rescheduling for one scraper."""
    name = module.NAME

    def _job():
        state_before = scraper_status.get(name)
        was_in_backoff = state_before.in_backoff
        module.run()
        state_after = scraper_status.get(name)
        is_in_backoff = state_after.in_backoff
        if was_in_backoff != is_in_backoff and _scheduler is not None:
            seconds = backoff if is_in_backoff else healthy
            try:
                _scheduler.reschedule_job(job_id, trigger="interval", seconds=seconds)
                logger.info("%s job rescheduled to %ss (backoff=%s)", name, seconds, is_in_backoff)
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not reschedule %s: %s", name, exc)

    _job.__name__ = f"_{name}_job"
    return _job


def run_scraper_now(name: str) -> dict:
    """Trigger a scraper synchronously, outside the scheduler. Used by the
    admin /run-once endpoint. Returns the scraper's run() summary dict.
    Raises ValueError if the name is unknown."""
    for module, _, _, _ in _SCRAPER_REGISTRY:
        if module.NAME == name:
            return module.run()
    raise ValueError(f"unknown scraper: {name}")


def known_scrapers() -> list[str]:
    return [m.NAME for m, *_ in _SCRAPER_REGISTRY]


def _backup_job() -> None:
    """Daily snapshot. Errors are logged inside backup_now and don't raise
    out of here — the scheduler should keep running even if one snapshot
    fails (e.g. disk briefly full)."""
    try:
        dest = db.backup_now(reason="scheduled-daily")
        pruned = db.prune_old_backups()
        logger.info(
            "daily backup complete: %s (pruned %d old)",
            dest.name, pruned,
        )
    except FileNotFoundError:
        logger.warning("daily backup skipped — no DB file to back up")
    except Exception as exc:  # noqa: BLE001
        logger.exception("daily backup failed: %s", exc)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()

    # Steam refresh — independent of social scrapers.
    _scheduler.add_job(
        steam.refresh_now,
        "interval",
        seconds=config.STEAM_REFRESH_SECONDS,
        id="steam_refresh",
        max_instances=1,
        coalesce=True,
    )

    # Daily DB backup at 03:00 local time. Cron-style so it lands at the
    # same wall-clock time every day instead of drifting if uvicorn restarts.
    _scheduler.add_job(
        _backup_job,
        CronTrigger(hour=3, minute=0),
        id="daily_db_backup",
        max_instances=1,
        coalesce=True,
    )

    # Make sure every scraper has a row before any first run.
    for module, *_ in _SCRAPER_REGISTRY:
        scraper_status.ensure(module.NAME)

    # Register all 5 social scrapers.
    for module, job_id, healthy, _backoff in _SCRAPER_REGISTRY:
        _scheduler.add_job(
            _wrap(module, job_id, healthy, _backoff),
            "interval",
            seconds=healthy,
            id=job_id,
            max_instances=1,
            coalesce=True,
            next_run_time=None,  # don't fire immediately at startup
        )

    _scheduler.start()
    logger.info(
        "scheduler started: steam=%ss, daily-backup=03:00, scrapers=%s",
        config.STEAM_REFRESH_SECONDS,
        ", ".join(f"{m.NAME}={s}s" for m, _, s, _ in _SCRAPER_REGISTRY),
    )

    # Run an initial backup at boot if there are no backups yet — gives us
    # a known-good snapshot from minute one without waiting for 03:00.
    if not db.list_backups():
        try:
            db.backup_now(reason="first-boot")
            logger.info("initial backup snapshot created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("initial backup failed: %s", exc)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

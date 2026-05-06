"""DB-backed scraper run-state tracker.

Backed by the `scraper_status` table. Public API kept compatible with the
old in-memory module so existing callers (Bluesky scraper, scheduler) don't
need to change much:

  state = scraper_status.get(name)
  state.record_success(inserted)
  state.record_failure(error)
  state.set_auth_state(state)         # NEW: 'ok' | 'auth-failed' | 'stub-credentials'
  state.in_backoff                    # bool, True after 3+ consecutive failures
  state.consecutive_failures          # int

scraper_status.all_states() returns a list of dicts for the admin endpoint.
scraper_status.ensure(name) creates a row with default values if missing.

Each call hits SQLite. That's fine — scrapers run on minute timescales, not
per-request, so the IO is negligible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from .db import engine

VALID_AUTH_STATES = {"ok", "auth-failed", "stub-credentials"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure(name: str) -> None:
    """Make sure a row exists for this scraper. Cheap if it already does."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO scraper_status (name, auth_state) "
                "VALUES (:name, 'ok')"
            ),
            {"name": name},
        )


@dataclass
class ScraperState:
    """Thin facade — every method writes immediately to the DB row.
    The dataclass attributes are a snapshot at construction time, so don't
    treat them as live (re-fetch via scraper_status.get(name) if you need fresh)."""
    name: str
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    auth_state: str = "ok"
    last_inserted: int = 0
    runs: int = 0
    successes: int = 0
    failures: int = 0

    @property
    def in_backoff(self) -> bool:
        return self.consecutive_failures >= 3

    def record_success(self, inserted: int = 0) -> None:
        now = _now()
        self.last_run = now
        self.last_success = now
        self.last_inserted = inserted
        self.consecutive_failures = 0
        self.auth_state = "ok" if self.auth_state != "stub-credentials" else self.auth_state
        self.runs += 1
        self.successes += 1
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE scraper_status SET "
                    "  last_run = :now, last_success = :now, last_inserted = :inserted, "
                    "  consecutive_failures = 0, runs = runs + 1, successes = successes + 1, "
                    "  auth_state = CASE WHEN auth_state = 'stub-credentials' "
                    "                    THEN 'stub-credentials' ELSE 'ok' END "
                    "WHERE name = :name"
                ),
                {"now": now, "inserted": inserted, "name": self.name},
            )

    def record_failure(self, error: str) -> None:
        now = _now()
        msg = (error or "")[:500]
        self.last_run = now
        self.last_error = msg
        self.consecutive_failures += 1
        self.runs += 1
        self.failures += 1
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE scraper_status SET "
                    "  last_run = :now, last_error = :err, "
                    "  consecutive_failures = consecutive_failures + 1, "
                    "  runs = runs + 1, failures = failures + 1 "
                    "WHERE name = :name"
                ),
                {"now": now, "err": msg, "name": self.name},
            )

    def set_auth_state(self, new_state: str) -> None:
        if new_state not in VALID_AUTH_STATES:
            raise ValueError(f"unknown auth_state: {new_state}")
        self.auth_state = new_state
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE scraper_status SET auth_state = :s WHERE name = :name"),
                {"s": new_state, "name": self.name},
            )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "last_run": self.last_run,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "auth_state": self.auth_state,
            "last_inserted": self.last_inserted,
            "runs": self.runs,
            "successes": self.successes,
            "failures": self.failures,
            "in_backoff": self.in_backoff,
        }


def _row_to_state(row) -> ScraperState:
    return ScraperState(
        name=row.name,
        last_run=row.last_run,
        last_success=row.last_success,
        last_error=row.last_error,
        consecutive_failures=row.consecutive_failures or 0,
        auth_state=row.auth_state or "ok",
        last_inserted=row.last_inserted or 0,
        runs=row.runs or 0,
        successes=row.successes or 0,
        failures=row.failures or 0,
    )


def get(name: str) -> ScraperState:
    """Fetch the state from DB, creating an empty row if missing."""
    ensure(name)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT name, last_run, last_success, last_error, consecutive_failures, "
                "       auth_state, last_inserted, runs, successes, failures "
                "FROM scraper_status WHERE name = :name"
            ),
            {"name": name},
        ).first()
    return _row_to_state(row)


def all_states() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, last_run, last_success, last_error, consecutive_failures, "
                "       auth_state, last_inserted, runs, successes, failures "
                "FROM scraper_status ORDER BY name"
            )
        ).all()
    return [_row_to_state(r).to_dict() for r in rows]

"""In-memory tracker for scraper run state.

Each scraper module reports begin/success/failure here. The /api/admin/scraper-status
endpoint exposes the current state. Backoff logic also reads from here so a
scraper with 3+ consecutive failures gets pushed to a slower interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ScraperState:
    name: str
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    runs: int = 0
    successes: int = 0
    failures: int = 0
    last_inserted: int = 0
    in_backoff: bool = False
    history: list[dict] = field(default_factory=list)

    def record_success(self, inserted: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.last_run = now
        self.last_success = now
        self.last_inserted = inserted
        self.consecutive_failures = 0
        self.in_backoff = False
        self.runs += 1
        self.successes += 1
        self.history.append({"ts": now, "ok": True, "inserted": inserted})
        self._trim()

    def record_failure(self, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.last_run = now
        self.last_error = error[:500]
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.in_backoff = True
        self.runs += 1
        self.failures += 1
        self.history.append({"ts": now, "ok": False, "error": self.last_error})
        self._trim()

    def _trim(self) -> None:
        # Keep the last 20 runs in memory.
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "last_run": self.last_run,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "runs": self.runs,
            "successes": self.successes,
            "failures": self.failures,
            "last_inserted": self.last_inserted,
            "in_backoff": self.in_backoff,
            "history": list(self.history),
        }


STATES: dict[str, ScraperState] = {}


def get(name: str) -> ScraperState:
    if name not in STATES:
        STATES[name] = ScraperState(name=name)
    return STATES[name]


def all_states() -> list[dict]:
    return [s.to_dict() for s in STATES.values()]

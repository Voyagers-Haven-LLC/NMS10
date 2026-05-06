"""SQLite engine, session, and schema bootstrap.

The DB lives at <repo-root>/data/nms10.db (or wherever NMS10_DATA_DIR points).
Schema is applied on startup; CREATE TABLE IF NOT EXISTS so safe on every boot.

Also exports backup helpers (snapshot via SQLite's online backup API) used by
the daily scheduled job and admin destructive-action preflight hooks.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("nms10.db")

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
# Honour the same NMS10_DATA_DIR override config.py uses, so Docker mounts
# work and the backup script snapshots the same file the app reads from.
DATA_DIR = Path(os.environ.get("NMS10_DATA_DIR", str(REPO_ROOT / "data"))).resolve()
DB_PATH = DATA_DIR / "nms10.db"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_LOG = DATA_DIR / "logs" / "backup.log"
BACKUP_RETAIN_DAYS = 30

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bases (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  builder_name TEXT NOT NULL,
  builder_affiliation TEXT,
  description TEXT,
  builder_notes TEXT,
  platform TEXT,
  galaxy TEXT,
  region TEXT,
  portal_address TEXT,
  tags TEXT,
  hero_image_path TEXT,
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved_at TIMESTAMP,
  status TEXT DEFAULT 'pending',
  submitter_email TEXT,
  submitter_discord_id TEXT,
  view_count INTEGER DEFAULT 0,
  star_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS base_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  base_id TEXT REFERENCES bases(id),
  image_path TEXT,
  caption TEXT,
  display_order INTEGER
);

CREATE TABLE IF NOT EXISTS communities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  language TEXT,
  description TEXT,
  link_url TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meetups (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  region TEXT,
  location TEXT,
  latitude REAL,
  longitude REAL,
  starts_at TIMESTAMP,
  description TEXT,
  organizer_name TEXT,
  contact_url TEXT,
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS social_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  author_name TEXT,
  author_handle TEXT,
  author_avatar_path TEXT,
  content TEXT,
  media_path TEXT,
  external_url TEXT,
  posted_at TIMESTAMP,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  featured BOOLEAN DEFAULT 0,
  hidden BOOLEAN DEFAULT 0,
  UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS admin_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS steam_cache (
  id INTEGER PRIMARY KEY,
  player_count INTEGER,
  fetched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraper_status (
  name TEXT PRIMARY KEY,
  last_run TIMESTAMP,
  last_success TIMESTAMP,
  last_error TEXT,
  consecutive_failures INTEGER DEFAULT 0,
  auth_state TEXT DEFAULT 'ok',
  last_inserted INTEGER DEFAULT 0,
  runs INTEGER DEFAULT 0,
  successes INTEGER DEFAULT 0,
  failures INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bases_status ON bases(status);
CREATE INDEX IF NOT EXISTS idx_bases_platform ON bases(platform);
CREATE INDEX IF NOT EXISTS idx_social_posts_source ON social_posts(source);
CREATE INDEX IF NOT EXISTS idx_social_posts_posted ON social_posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_meetups_region ON meetups(region);
"""


def init_db() -> None:
    """Apply the schema. Every CREATE uses IF NOT EXISTS so this is safe to
    run on every startup — new tables get added to existing DBs without
    losing data, brand-new DBs get the full schema. Acts as a poor man's
    migration system."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Backup + safety helpers
# ============================================================================

def _backup_logger() -> logging.Logger:
    """Attach a file handler to /data/logs/backup.log the first time we
    log something. Idempotent."""
    BACKUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename) == BACKUP_LOG
        for h in logger.handlers
    ):
        h = logging.FileHandler(BACKUP_LOG, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


def backup_now(reason: Optional[str] = None) -> Path:
    """Snapshot the live DB to data/backups/nms10-YYYYMMDD-HHMMSS.db using
    SQLite's online backup API. Atomic, safe while the DB is in use.

    `reason` is appended to the log line so we can grep "manual delete" etc.
    Returns the path to the new backup file.

    Raises FileNotFoundError if DB_PATH doesn't exist (nothing to back up).
    """
    log = _backup_logger()
    if not DB_PATH.exists():
        log.warning("backup skipped — DB does not exist at %s", DB_PATH)
        raise FileNotFoundError(f"DB not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"nms10-{stamp}.db"
    # If two calls land in the same second (preflight + scheduled), append a
    # disambiguator rather than overwrite.
    n = 1
    while dest.exists():
        dest = BACKUP_DIR / f"nms10-{stamp}-{n}.db"
        n += 1

    src = sqlite3.connect(str(DB_PATH))
    try:
        # Touch the destination first so it exists for the backup API.
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    size = dest.stat().st_size
    suffix = f" reason={reason!r}" if reason else ""
    log.info("backup OK -> %s (%d bytes)%s", dest.name, size, suffix)
    return dest


def prune_old_backups(retain_days: int = BACKUP_RETAIN_DAYS) -> int:
    """Delete backups older than retain_days. Returns count deleted."""
    log = _backup_logger()
    if not BACKUP_DIR.exists():
        return 0
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retain_days)
    deleted = 0
    for p in BACKUP_DIR.glob("nms10-*.db"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                p.unlink()
                log.info("pruned old backup %s (mtime=%s)", p.name, mtime.isoformat())
                deleted += 1
            except OSError as exc:
                log.warning("failed to prune %s: %s", p.name, exc)
    return deleted


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("nms10-*.db"))


def preflight_backup(reason: str) -> Optional[Path]:
    """Snapshot the DB before any destructive operation. Returns the backup
    path on success, None if the DB doesn't exist (nothing to snapshot).
    Errors are logged but do NOT raise — we don't want to block a delete
    because the disk is briefly full. The 30-day backup history at least
    means we still have yesterday's snapshot.
    """
    try:
        return backup_now(reason=f"preflight: {reason}")
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 — never block the calling op
        _backup_logger().error("preflight backup failed for %s: %s", reason, exc)
        return None


def refuse_to_wipe_unless_explicit(action: str) -> None:
    """Tripwire — call this before any code path that would delete or
    replace nms10.db. Raises RuntimeError unless NMS10_ALLOW_DB_WIPE=yes
    is in the environment.

    Currently no internal code path needs this (there are no destructive
    helpers), but future contributors who think they're being clever
    should hit this first. Leave it loud."""
    if os.environ.get("NMS10_ALLOW_DB_WIPE") != "yes":
        raise RuntimeError(
            f"Refusing to wipe DB ({action}) without NMS10_ALLOW_DB_WIPE=yes "
            f"opt-in. This is a tripwire — see docs/RESTORE.md before overriding."
        )

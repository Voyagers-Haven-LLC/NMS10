"""SQLite engine, session, and schema bootstrap.

The DB lives at <repo-root>/data/nms10.db. Schema is applied on startup if the
DB file doesn't yet exist (or, defensively, if the file exists but is empty).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "nms10.db"

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

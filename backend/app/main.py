"""FastAPI entry point for the NMS10 backend.

For now this only exposes /api/health and bootstraps the SQLite schema on
startup. Public read endpoints, submission endpoints, admin auth, scraper
scheduling, and the Steam-count proxy land in later sessions per the roadmap.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import DB_PATH, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="NMS10 API", version="0.0.1", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/_meta")
def meta() -> dict[str, str]:
    return {"db_path": str(DB_PATH), "version": app.version}

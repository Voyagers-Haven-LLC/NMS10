"""Cached Steam concurrent player count."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..db import engine

router = APIRouter()


@router.get("/steam-count")
def get_steam_count() -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT player_count, fetched_at FROM steam_cache WHERE id = 1")
        ).first()
    if row is None:
        return {"player_count": None, "fetched_at": None}
    return {"player_count": row.player_count, "fetched_at": row.fetched_at}

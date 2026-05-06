"""Public socials feed."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import engine

router = APIRouter()


def _row(row) -> dict:
    return {
        "id": row.id,
        "source": row.source,
        "external_id": row.external_id,
        "author_name": row.author_name,
        "author_handle": row.author_handle,
        "author_avatar_path": row.author_avatar_path,
        "content": row.content,
        "media_path": row.media_path,
        "external_url": row.external_url,
        "posted_at": row.posted_at,
        "fetched_at": row.fetched_at,
        "featured": bool(row.featured),
        "hidden": bool(row.hidden),
    }


@router.get("/socials")
def list_socials(source: Optional[str] = Query(default=None)) -> list[dict]:
    sql = (
        "SELECT id, source, external_id, author_name, author_handle, author_avatar_path, "
        "       content, media_path, external_url, posted_at, fetched_at, featured, hidden "
        "FROM social_posts WHERE hidden = 0"
    )
    params: dict = {}
    if source and source != "all":
        sql += " AND source = :source"
        params["source"] = source
    sql += " ORDER BY featured DESC, COALESCE(posted_at, fetched_at) DESC"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).all()
    return [_row(r) for r in rows]

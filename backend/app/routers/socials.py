"""Public socials feed + URL-submission endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text

from .. import config
from ..db import engine
from ..notifications import notify_bot
from ..og import fetch_og, stable_external_id
from ..rate_limit import limiter
from ..schemas import SocialUrlSubmission

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


@router.post("/submissions/socials", status_code=201)
@limiter.limit(config.SUBMISSION_RATE_LIMIT)
def submit_social(request: Request, payload: SocialUrlSubmission) -> dict:
    """Accept a pasted URL, fetch Open Graph, queue for moderation (hidden=true).

    Re-submitting the same URL returns the existing row instead of erroring,
    so the bot doesn't have to dedupe client-side."""
    url = payload.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")
    og = fetch_og(url)
    external_id = stable_external_id(url)
    source = og["source"]
    content = og["title"] or url
    if og["description"]:
        content = f"{content}\n{og['description']}" if content else og["description"]
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM social_posts WHERE source = :s AND external_id = :e"),
            {"s": source, "e": external_id},
        ).first()
        if existing is not None:
            return {"id": existing.id, "source": source, "external_id": external_id, "duplicate": True}
        result = conn.execute(
            text(
                "INSERT INTO social_posts (source, external_id, author_name, author_handle, "
                "  content, external_url, posted_at, fetched_at, media_path, featured, hidden) "
                "VALUES (:source, :external_id, :author_name, :author_handle, :content, "
                "  :external_url, :posted_at, :fetched_at, :media_path, 0, 1)"
            ),
            {
                "source": source,
                "external_id": external_id,
                "author_name": og["site_name"] or payload.submitter_name,
                "author_handle": payload.submitter_discord_id,
                "content": content[:2000] if content else None,
                "external_url": url,
                "posted_at": now,
                "fetched_at": now,
                "media_path": og["image"],
            },
        )
    new_id = result.lastrowid
    notify_bot(
        "submission",
        {
            "entity": "social",
            "id": new_id,
            "source": source,
            "external_url": url,
            "submitter_discord_id": payload.submitter_discord_id,
            "title": og["title"],
        },
    )
    return {"id": new_id, "source": source, "external_id": external_id, "duplicate": False}

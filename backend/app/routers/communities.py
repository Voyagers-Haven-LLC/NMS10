"""Public communities endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from .. import config
from ..db import engine
from ..notifications import notify_bot
from ..rate_limit import limiter
from ..schemas import CommunitySubmission
from ..utils import slugify

router = APIRouter()


def _row(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "language": row.language,
        "description": row.description,
        "link_url": row.link_url,
        "approved": bool(row.approved),
    }


@router.get("/communities")
def list_communities() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, language, description, link_url, approved "
                "FROM communities WHERE approved = 1 ORDER BY added_at ASC"
            )
        ).all()
    return [_row(r) for r in rows]


@router.post("/submissions/communities", status_code=201)
@limiter.limit(config.SUBMISSION_RATE_LIMIT)
def submit_community(request: Request, payload: CommunitySubmission) -> dict:
    cid = slugify(payload.name)
    with engine.begin() as conn:
        suffix = 1
        unique = cid
        while conn.execute(text("SELECT 1 FROM communities WHERE id = :id"), {"id": unique}).first():
            suffix += 1
            unique = f"{cid}-{suffix}"
        conn.execute(
            text(
                "INSERT INTO communities (id, name, language, description, link_url, approved) "
                "VALUES (:id, :name, :language, :description, :link_url, 0)"
            ),
            {
                "id": unique,
                "name": payload.name,
                "language": payload.language,
                "description": payload.description,
                "link_url": payload.link_url,
            },
        )
    notify_bot(
        "submission",
        {"entity": "community", "id": unique, "name": payload.name, "language": payload.language},
    )
    return {"id": unique, "approved": False}

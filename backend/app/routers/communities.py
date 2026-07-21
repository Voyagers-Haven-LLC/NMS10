"""Public communities endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sqlalchemy import text

from .. import config
from ..db import engine
from ..media import community_logo_rel, save_community_logo
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
        "logo_image_path": row.logo_image_path,
        "approved": bool(row.approved),
    }


@router.get("/communities")
def list_communities() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, language, description, link_url, logo_image_path, approved "
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


@router.post("/submissions/communities/{cid}/logo", status_code=201)
@limiter.limit(config.IMAGE_UPLOAD_RATE_LIMIT)
def submit_community_logo(request: Request, cid: str, file: UploadFile = File(...)) -> dict:
    """Attach a logo to a just-submitted community. Mirrors base photo upload:
    only accepted while the community is still unapproved (pending review), so
    a human vets it before it goes public. Rate-limited + re-encoded."""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT approved FROM communities WHERE id = :id"), {"id": cid}
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="community not found")
        if row.approved:
            raise HTTPException(
                status_code=409,
                detail="a logo can only be added while a submission is pending review",
            )
        dest = save_community_logo(cid, file)
        rel = community_logo_rel(cid, dest)
        conn.execute(
            text("UPDATE communities SET logo_image_path = :p WHERE id = :id"),
            {"p": rel, "id": cid},
        )
    return {"logo_image_path": rel}

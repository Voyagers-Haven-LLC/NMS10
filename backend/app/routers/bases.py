"""Public base endpoints: list approved bases (with filters), single detail
(increments view_count), and the public submission endpoint."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import text

from .. import config
from ..db import engine
from ..media import save_processed_image
from ..notifications import notify_bot
from ..rate_limit import limiter
from ..schemas import BaseSubmission
from ..utils import (
    builder_initials,
    format_count,
    format_stars,
    format_submitted,
    hero_color_for,
    join_tags,
    slugify,
    split_tags,
)

router = APIRouter()


def _row_to_card(row) -> dict:
    """Shape a base row for the bases-grid card consumption."""
    return {
        "id": row.id,
        "title": row.title,
        "builder_name": row.builder_name,
        "builder_initials": builder_initials(row.builder_name or ""),
        "builder_affiliation": row.builder_affiliation,
        "description": row.description,
        "blurb": (row.description or "").split("\n", 1)[0][:200],
        "platform": row.platform,
        "galaxy": row.galaxy,
        "region": row.region,
        "portal_address": row.portal_address,
        "tags": split_tags(row.tags),
        "hero_image_path": row.hero_image_path,
        "hero_color": hero_color_for(row.id),
        "star_count": row.star_count or 0,
        "view_count": row.view_count or 0,
        "stars_display": format_stars(row.star_count),
        "visits_display": format_count(row.view_count),
        "submitted_display": format_submitted(row.submitted_at),
        "status": row.status,
    }


@router.get("/bases")
def list_bases(
    platform: Optional[str] = Query(default=None),
    tags: Optional[str] = Query(default=None),
) -> list[dict]:
    sql = (
        "SELECT id, title, builder_name, builder_affiliation, description, "
        "       builder_notes, platform, galaxy, region, "
        "       portal_address, tags, hero_image_path, submitted_at, "
        "       approved_at, status, view_count, star_count "
        "FROM bases WHERE status = 'approved' ORDER BY approved_at DESC, submitted_at DESC"
    )
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).all()
    items = [_row_to_card(r) for r in rows]
    if platform and platform != "all":
        items = [b for b in items if b["platform"] == platform]
    if tags:
        wanted = {t for t in tags.split(",") if t}
        items = [b for b in items if wanted.issubset(set(b["tags"]))]
    return items


@router.get("/bases/{base_id}")
def get_base(base_id: str) -> dict:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, title, builder_name, builder_affiliation, description, "
                "       builder_notes, platform, galaxy, region, "
                "       portal_address, tags, hero_image_path, submitted_at, "
                "       approved_at, status, view_count, star_count "
                "FROM bases WHERE id = :id AND status = 'approved'"
            ),
            {"id": base_id},
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="base not found")
        conn.execute(
            text("UPDATE bases SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :id"),
            {"id": base_id},
        )

    card = _row_to_card(row)
    card["builder_notes"] = row.builder_notes
    card["view_count"] = (row.view_count or 0) + 1
    card["visits_display"] = format_count(card["view_count"])

    with engine.connect() as conn:
        images = conn.execute(
            text(
                "SELECT image_path, caption FROM base_images "
                "WHERE base_id = :id ORDER BY display_order ASC, id ASC"
            ),
            {"id": base_id},
        ).all()
    card["images"] = [{"image_path": i.image_path, "caption": i.caption} for i in images]
    return card


@router.post("/submissions/bases", status_code=201)
@limiter.limit(config.SUBMISSION_RATE_LIMIT)
def submit_base(request: Request, payload: BaseSubmission) -> dict:
    base_id = slugify(payload.title)
    # Make id unique if collision
    with engine.begin() as conn:
        suffix = 1
        unique_id = base_id
        while conn.execute(text("SELECT 1 FROM bases WHERE id = :id"), {"id": unique_id}).first():
            suffix += 1
            unique_id = f"{base_id}-{suffix}"
        data = payload.model_dump(by_alias=True)
        conn.execute(
            text(
                "INSERT INTO bases (id, title, builder_name, builder_affiliation, "
                "  description, builder_notes, platform, galaxy, region, "
                "  portal_address, tags, status, submitter_email, submitter_discord_id) "
                "VALUES (:id, :title, :builder_name, :builder_affiliation, :description, "
                "  :builder_notes, :platform, :galaxy, :region, :portal_address, "
                "  :tags, 'pending', :submitter_email, :submitter_discord_id)"
            ),
            {
                "id": unique_id,
                "title": data["title"],
                "builder_name": data["builder_name"],
                "builder_affiliation": data.get("builder_affiliation"),
                "description": data.get("description"),
                "builder_notes": data.get("builder_notes"),
                "platform": data.get("platform"),
                "galaxy": data.get("galaxy"),
                "region": data.get("region"),
                "portal_address": data.get("portal_address"),
                "tags": join_tags(data.get("tags")),
                "submitter_email": data.get("submitter_email"),
                "submitter_discord_id": data.get("submitter_discord_id"),
            },
        )
    notify_bot(
        "submission",
        {
            "entity": "base",
            "id": unique_id,
            "title": data["title"],
            "builder_name": data["builder_name"],
            "platform": data.get("platform"),
            "submitter_discord_id": data.get("submitter_discord_id"),
        },
    )
    return {"id": unique_id, "status": "pending"}


# --- public base image upload (attach photos to a just-submitted base) ---
#
# Photos attach only while the base is still 'pending' (i.e. sitting in the
# moderation queue). Once a moderator approves or rejects it, the public upload
# door closes. Combined with the moderation gate and the per-IP rate limit, that
# bounds abuse: the worst a griefer can do is add images to their own pending
# submission, which a human reviews before anything goes public. Everything runs
# through media.save_processed_image (type/size checks + downscale + re-encode).

MAX_GALLERY_PER_BASE = 4


def _require_pending(conn, base_id: str):
    row = conn.execute(text("SELECT status FROM bases WHERE id = :id"), {"id": base_id}).first()
    if row is None:
        raise HTTPException(status_code=404, detail="base not found")
    if row.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="photos can only be added while a submission is pending review",
        )


@router.post("/submissions/bases/{base_id}/hero", status_code=201)
@limiter.limit(config.IMAGE_UPLOAD_RATE_LIMIT)
def submit_base_hero(request: Request, base_id: str, file: UploadFile = File(...)) -> dict:
    with engine.begin() as conn:
        _require_pending(conn, base_id)
        dest = save_processed_image(base_id, file)
        rel = f"/media/{base_id}/{dest.name}"
        conn.execute(
            text("UPDATE bases SET hero_image_path = :p WHERE id = :id"),
            {"p": rel, "id": base_id},
        )
    return {"hero_image_path": rel}


@router.post("/submissions/bases/{base_id}/gallery", status_code=201)
@limiter.limit(config.IMAGE_UPLOAD_RATE_LIMIT)
def submit_base_gallery(request: Request, base_id: str, file: UploadFile = File(...)) -> dict:
    with engine.begin() as conn:
        _require_pending(conn, base_id)
        count = conn.execute(
            text("SELECT COUNT(*) FROM base_images WHERE base_id = :id"), {"id": base_id}
        ).scalar() or 0
        if count >= MAX_GALLERY_PER_BASE:
            raise HTTPException(
                status_code=409,
                detail=f"gallery limit reached ({MAX_GALLERY_PER_BASE} photos max)",
            )
        dest = save_processed_image(base_id, file)
        rel = f"/media/{base_id}/{dest.name}"
        order = conn.execute(
            text("SELECT COALESCE(MAX(display_order), 0) + 1 FROM base_images WHERE base_id = :id"),
            {"id": base_id},
        ).scalar()
        result = conn.execute(
            text(
                "INSERT INTO base_images (base_id, image_path, caption, display_order) "
                "VALUES (:b, :p, NULL, :o)"
            ),
            {"b": base_id, "p": rel, "o": order},
        )
    return {"id": result.lastrowid, "image_path": rel, "display_order": order}

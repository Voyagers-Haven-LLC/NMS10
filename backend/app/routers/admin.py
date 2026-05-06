"""Admin endpoints: login, queue, CRUD for bases/communities/meetups/socials,
and image upload for bases."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from .. import auth, config
from ..db import engine
from ..notifications import notify_bot
from ..schemas import (
    BaseAdminUpsert,
    CommunityAdminUpsert,
    LoginPayload,
    MeetupAdminUpsert,
    SocialAdminUpsert,
)
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


# --- login ---

@router.post("/admin/login")
def login(payload: LoginPayload) -> dict:
    user = auth.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = auth.issue_token(user["id"], user["username"])
    return {**token, "username": user["username"]}


@router.post("/admin/logout")
def logout(_user: dict = Depends(auth.require_admin)) -> dict:
    return {"ok": True}


# --- queue ---

@router.get("/admin/queue")
def get_queue(_user: dict = Depends(auth.require_admin)) -> dict:
    with engine.connect() as conn:
        bases = conn.execute(
            text(
                "SELECT id, title, builder_name, platform, submitted_at, status "
                "FROM bases WHERE status = 'pending' ORDER BY submitted_at DESC"
            )
        ).all()
        communities = conn.execute(
            text(
                "SELECT id, name, language, added_at, approved "
                "FROM communities WHERE approved = 0 ORDER BY added_at DESC"
            )
        ).all()
        meetups = conn.execute(
            text(
                "SELECT id, title, region, location, submitted_at, approved "
                "FROM meetups WHERE approved = 0 ORDER BY submitted_at DESC"
            )
        ).all()
    return {
        "bases": [
            {
                "id": b.id,
                "title": b.title,
                "builder_name": b.builder_name,
                "platform": b.platform,
                "submitted_at": b.submitted_at,
                "status": b.status,
            }
            for b in bases
        ],
        "communities": [
            {
                "id": c.id,
                "name": c.name,
                "language": c.language,
                "added_at": c.added_at,
            }
            for c in communities
        ],
        "meetups": [
            {
                "id": m.id,
                "title": m.title,
                "region": m.region,
                "location": m.location,
                "submitted_at": m.submitted_at,
            }
            for m in meetups
        ],
    }


# --- bases CRUD ---

def _load_base_admin(conn, base_id: str) -> dict:
    row = conn.execute(
        text(
            "SELECT id, title, builder_name, builder_affiliation, description, "
            "       builder_notes, platform, galaxy, region, "
            "       portal_address, tags, hero_image_path, submitted_at, "
            "       approved_at, status, view_count, star_count "
            "FROM bases WHERE id = :id"
        ),
        {"id": base_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="base not found")
    images = conn.execute(
        text(
            "SELECT id, image_path, caption, display_order FROM base_images "
            "WHERE base_id = :id ORDER BY display_order ASC, id ASC"
        ),
        {"id": base_id},
    ).all()
    return {
        "id": row.id,
        "title": row.title,
        "builder_name": row.builder_name,
        "builder_initials": builder_initials(row.builder_name or ""),
        "builder_affiliation": row.builder_affiliation,
        "description": row.description,
        "builder_notes": row.builder_notes,
        "platform": row.platform,
        "galaxy": row.galaxy,
        "region": row.region,
        "portal_address": row.portal_address,
        "tags": split_tags(row.tags),
        "hero_image_path": row.hero_image_path,
        "hero_color": hero_color_for(row.id),
        "submitted_at": row.submitted_at,
        "submitted_display": format_submitted(row.submitted_at),
        "approved_at": row.approved_at,
        "status": row.status,
        "view_count": row.view_count or 0,
        "star_count": row.star_count or 0,
        "stars_display": format_stars(row.star_count),
        "visits_display": format_count(row.view_count),
        "images": [
            {"id": i.id, "image_path": i.image_path, "caption": i.caption, "display_order": i.display_order}
            for i in images
        ],
    }


@router.get("/admin/bases")
def admin_list_bases(_user: dict = Depends(auth.require_admin)) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, title, builder_name, platform, status, submitted_at, "
                "       approved_at, view_count, star_count "
                "FROM bases ORDER BY submitted_at DESC"
            )
        ).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "builder_name": r.builder_name,
            "platform": r.platform,
            "status": r.status,
            "submitted_at": r.submitted_at,
            "approved_at": r.approved_at,
            "view_count": r.view_count or 0,
            "star_count": r.star_count or 0,
        }
        for r in rows
    ]


@router.get("/admin/bases/{base_id}")
def admin_get_base(base_id: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.connect() as conn:
        return _load_base_admin(conn, base_id)


@router.post("/admin/bases", status_code=201)
def admin_create_base(payload: BaseAdminUpsert, _user: dict = Depends(auth.require_admin)) -> dict:
    if not payload.title or not payload.builder_name:
        raise HTTPException(status_code=422, detail="title and builder_name are required")
    base_id = (payload.id and payload.id.strip()) or slugify(payload.title)
    data = payload.model_dump(by_alias=True)
    with engine.begin() as conn:
        suffix = 1
        unique = base_id
        while conn.execute(text("SELECT 1 FROM bases WHERE id = :id"), {"id": unique}).first():
            suffix += 1
            unique = f"{base_id}-{suffix}"
        status_val = data.get("status") or "approved"
        approved_at = datetime.now(timezone.utc).isoformat() if status_val == "approved" else None
        conn.execute(
            text(
                "INSERT INTO bases (id, title, builder_name, builder_affiliation, "
                "  description, builder_notes, platform, galaxy, region, "
                "  portal_address, tags, hero_image_path, status, approved_at, "
                "  view_count, star_count) "
                "VALUES (:id, :title, :builder_name, :builder_affiliation, :description, "
                "  :builder_notes, :platform, :galaxy, :region, :portal_address, "
                "  :tags, :hero_image_path, :status, :approved_at, :view_count, :star_count)"
            ),
            {
                "id": unique,
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
                "hero_image_path": data.get("hero_image_path"),
                "status": status_val,
                "approved_at": approved_at,
                "view_count": data.get("view_count") or 0,
                "star_count": data.get("star_count") or 0,
            },
        )
        return _load_base_admin(conn, unique)


@router.put("/admin/bases/{base_id}")
def admin_update_base(
    base_id: str,
    payload: BaseAdminUpsert,
    _user: dict = Depends(auth.require_admin),
) -> dict:
    data = payload.model_dump(by_alias=True, exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="no fields to update")
    field_map = {
        "title": "title",
        "builder_name": "builder_name",
        "builder_affiliation": "builder_affiliation",
        "description": "description",
        "builder_notes": "builder_notes",
        "platform": "platform",
        "galaxy": "galaxy",
        "region": "region",
        "portal_address": "portal_address",
        "hero_image_path": "hero_image_path",
        "status": "status",
        "view_count": "view_count",
        "star_count": "star_count",
    }
    sets = []
    params: dict = {"id": base_id}
    for key, col in field_map.items():
        if key in data:
            sets.append(f"{col} = :{col.replace(' ', '_')}")
            params[col.replace(" ", "_")] = data[key]
    if "tags" in data:
        sets.append("tags = :tags_str")
        params["tags_str"] = join_tags(data["tags"])
    if "status" in data and data["status"] == "approved":
        sets.append("approved_at = COALESCE(approved_at, :now)")
        params["now"] = datetime.now(timezone.utc).isoformat()
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sql = "UPDATE bases SET " + ", ".join(sets) + " WHERE id = :id"
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="base not found")
        return _load_base_admin(conn, base_id)


@router.post("/admin/bases/{base_id}/approve")
def admin_approve_base(base_id: str, _user: dict = Depends(auth.require_admin)) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE bases SET status = 'approved', approved_at = :now WHERE id = :id"),
            {"now": now, "id": base_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="base not found")
        loaded = _load_base_admin(conn, base_id)
    notify_bot(
        "approved",
        {
            "entity": "base",
            "id": loaded["id"],
            "title": loaded["title"],
            "builder_name": loaded["builder_name"],
            "platform": loaded["platform"],
            "url_path": f"/civs/bases/{loaded['id']}",
        },
    )
    return loaded


@router.post("/admin/bases/{base_id}/reject")
def admin_reject_base(base_id: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE bases SET status = 'rejected' WHERE id = :id"),
            {"id": base_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="base not found")
        return _load_base_admin(conn, base_id)


@router.delete("/admin/bases/{base_id}")
def admin_delete_base(base_id: str, _user: dict = Depends(auth.require_admin)) -> dict:
    media_dir = config.MEDIA_DIR / base_id
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM base_images WHERE base_id = :id"), {"id": base_id})
        result = conn.execute(text("DELETE FROM bases WHERE id = :id"), {"id": base_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="base not found")
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)
    return {"ok": True}


# --- base image upload ---

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _save_image(base_id: str, file: UploadFile) -> Path:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported image type: {file.content_type}")
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }[file.content_type]
    base_dir = config.MEDIA_DIR / base_id
    base_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    dest = base_dir / name
    written = 0
    with dest.open("wb") as out:
        while True:
            chunk = file.file.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_IMAGE_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="image too large (8MB max)")
            out.write(chunk)
    return dest


@router.post("/admin/bases/{base_id}/hero-image")
def admin_upload_hero(
    base_id: str,
    file: UploadFile = File(...),
    _user: dict = Depends(auth.require_admin),
) -> dict:
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT hero_image_path FROM bases WHERE id = :id"),
            {"id": base_id},
        ).first()
        if existing is None:
            raise HTTPException(status_code=404, detail="base not found")
        dest = _save_image(base_id, file)
        rel = f"/media/{base_id}/{dest.name}"
        conn.execute(
            text("UPDATE bases SET hero_image_path = :p WHERE id = :id"),
            {"p": rel, "id": base_id},
        )
    return {"hero_image_path": rel}


@router.post("/admin/bases/{base_id}/gallery")
def admin_upload_gallery(
    base_id: str,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(default=None),
    _user: dict = Depends(auth.require_admin),
) -> dict:
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT 1 FROM bases WHERE id = :id"), {"id": base_id}).first()
        if existing is None:
            raise HTTPException(status_code=404, detail="base not found")
        dest = _save_image(base_id, file)
        rel = f"/media/{base_id}/{dest.name}"
        order = conn.execute(
            text("SELECT COALESCE(MAX(display_order), 0) + 1 AS next FROM base_images WHERE base_id = :id"),
            {"id": base_id},
        ).scalar()
        result = conn.execute(
            text(
                "INSERT INTO base_images (base_id, image_path, caption, display_order) "
                "VALUES (:b, :p, :c, :o)"
            ),
            {"b": base_id, "p": rel, "c": caption, "o": order},
        )
        return {"id": result.lastrowid, "image_path": rel, "caption": caption, "display_order": order}


@router.delete("/admin/bases/{base_id}/gallery/{image_id}")
def admin_delete_gallery(
    base_id: str,
    image_id: int,
    _user: dict = Depends(auth.require_admin),
) -> dict:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT image_path FROM base_images WHERE id = :iid AND base_id = :bid"),
            {"iid": image_id, "bid": base_id},
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="image not found")
        conn.execute(text("DELETE FROM base_images WHERE id = :iid"), {"iid": image_id})
    if row.image_path and row.image_path.startswith("/media/"):
        rel = row.image_path[len("/media/"):]
        full = config.MEDIA_DIR / rel
        try:
            full.unlink()
        except FileNotFoundError:
            pass
    return {"ok": True}


# --- communities CRUD ---

def _community_row(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "language": row.language,
        "description": row.description,
        "link_url": row.link_url,
        "approved": bool(row.approved),
        "added_at": row.added_at,
    }


@router.get("/admin/communities")
def admin_list_communities(_user: dict = Depends(auth.require_admin)) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, language, description, link_url, approved, added_at "
                "FROM communities ORDER BY added_at DESC"
            )
        ).all()
    return [_community_row(r) for r in rows]


@router.post("/admin/communities", status_code=201)
def admin_create_community(payload: CommunityAdminUpsert, _user: dict = Depends(auth.require_admin)) -> dict:
    if not payload.name:
        raise HTTPException(status_code=422, detail="name is required")
    cid = (payload.id and payload.id.strip()) or slugify(payload.name)
    with engine.begin() as conn:
        suffix = 1
        unique = cid
        while conn.execute(text("SELECT 1 FROM communities WHERE id = :id"), {"id": unique}).first():
            suffix += 1
            unique = f"{cid}-{suffix}"
        approved_val = 1 if (payload.approved is None or payload.approved) else 0
        conn.execute(
            text(
                "INSERT INTO communities (id, name, language, description, link_url, approved) "
                "VALUES (:id, :name, :language, :description, :link_url, :approved)"
            ),
            {
                "id": unique,
                "name": payload.name,
                "language": payload.language,
                "description": payload.description,
                "link_url": payload.link_url,
                "approved": approved_val,
            },
        )
        row = conn.execute(
            text("SELECT id, name, language, description, link_url, approved, added_at FROM communities WHERE id = :id"),
            {"id": unique},
        ).first()
        return _community_row(row)


@router.put("/admin/communities/{cid}")
def admin_update_community(
    cid: str,
    payload: CommunityAdminUpsert,
    _user: dict = Depends(auth.require_admin),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    sets = []
    params: dict = {"id": cid}
    for col in ("name", "language", "description", "link_url"):
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = data[col]
    if "approved" in data:
        sets.append("approved = :approved")
        params["approved"] = 1 if data["approved"] else 0
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sql = "UPDATE communities SET " + ", ".join(sets) + " WHERE id = :id"
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="community not found")
        row = conn.execute(
            text("SELECT id, name, language, description, link_url, approved, added_at FROM communities WHERE id = :id"),
            {"id": cid},
        ).first()
        return _community_row(row)


@router.post("/admin/communities/{cid}/approve")
def admin_approve_community(cid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE communities SET approved = 1 WHERE id = :id"), {"id": cid})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="community not found")
        row = conn.execute(
            text("SELECT id, name, language, description, link_url, approved, added_at FROM communities WHERE id = :id"),
            {"id": cid},
        ).first()
        result_dict = _community_row(row)
    notify_bot(
        "approved",
        {"entity": "community", "id": result_dict["id"], "name": result_dict["name"], "url_path": "/civs"},
    )
    return result_dict


@router.post("/admin/communities/{cid}/reject")
def admin_reject_community(cid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    return admin_delete_community(cid, _user)  # rejecting an unapproved community = drop it


@router.delete("/admin/communities/{cid}")
def admin_delete_community(cid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM communities WHERE id = :id"), {"id": cid})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="community not found")
    return {"ok": True}


# --- meetups CRUD ---

def _meetup_row(row) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "region": row.region,
        "location": row.location,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "starts_at": row.starts_at,
        "description": row.description,
        "organizer_name": row.organizer_name,
        "contact_url": row.contact_url,
        "approved": bool(row.approved),
        "submitted_at": row.submitted_at,
    }


def _select_meetup(conn, mid: str):
    return conn.execute(
        text(
            "SELECT id, title, region, location, latitude, longitude, starts_at, "
            "       description, organizer_name, contact_url, approved, submitted_at "
            "FROM meetups WHERE id = :id"
        ),
        {"id": mid},
    ).first()


@router.get("/admin/meetups")
def admin_list_meetups(_user: dict = Depends(auth.require_admin)) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, title, region, location, latitude, longitude, starts_at, "
                "       description, organizer_name, contact_url, approved, submitted_at "
                "FROM meetups ORDER BY starts_at ASC"
            )
        ).all()
    return [_meetup_row(r) for r in rows]


@router.post("/admin/meetups", status_code=201)
def admin_create_meetup(payload: MeetupAdminUpsert, _user: dict = Depends(auth.require_admin)) -> dict:
    if not payload.title:
        raise HTTPException(status_code=422, detail="title is required")
    mid = (payload.id and payload.id.strip()) or slugify(payload.title)
    with engine.begin() as conn:
        suffix = 1
        unique = mid
        while conn.execute(text("SELECT 1 FROM meetups WHERE id = :id"), {"id": unique}).first():
            suffix += 1
            unique = f"{mid}-{suffix}"
        approved_val = 1 if (payload.approved is None or payload.approved) else 0
        conn.execute(
            text(
                "INSERT INTO meetups (id, title, region, location, latitude, longitude, "
                "  starts_at, description, organizer_name, contact_url, approved) "
                "VALUES (:id, :title, :region, :location, :latitude, :longitude, "
                "  :starts_at, :description, :organizer_name, :contact_url, :approved)"
            ),
            {
                "id": unique,
                "title": payload.title,
                "region": payload.region,
                "location": payload.location,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "starts_at": payload.starts_at,
                "description": payload.description,
                "organizer_name": payload.organizer_name,
                "contact_url": payload.contact_url,
                "approved": approved_val,
            },
        )
        return _meetup_row(_select_meetup(conn, unique))


@router.put("/admin/meetups/{mid}")
def admin_update_meetup(
    mid: str,
    payload: MeetupAdminUpsert,
    _user: dict = Depends(auth.require_admin),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    field_cols = (
        "title",
        "region",
        "location",
        "latitude",
        "longitude",
        "starts_at",
        "description",
        "organizer_name",
        "contact_url",
    )
    sets = []
    params: dict = {"id": mid}
    for col in field_cols:
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = data[col]
    if "approved" in data:
        sets.append("approved = :approved")
        params["approved"] = 1 if data["approved"] else 0
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sql = "UPDATE meetups SET " + ", ".join(sets) + " WHERE id = :id"
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="meetup not found")
        return _meetup_row(_select_meetup(conn, mid))


@router.post("/admin/meetups/{mid}/approve")
def admin_approve_meetup(mid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE meetups SET approved = 1 WHERE id = :id"), {"id": mid})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="meetup not found")
        loaded = _meetup_row(_select_meetup(conn, mid))
    notify_bot(
        "approved",
        {
            "entity": "meetup",
            "id": loaded["id"],
            "title": loaded["title"],
            "region": loaded["region"],
            "location": loaded["location"],
            "url_path": "/meetups",
        },
    )
    return loaded


@router.post("/admin/meetups/{mid}/reject")
def admin_reject_meetup(mid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    return admin_delete_meetup(mid, _user)


@router.delete("/admin/meetups/{mid}")
def admin_delete_meetup(mid: str, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM meetups WHERE id = :id"), {"id": mid})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="meetup not found")
    return {"ok": True}


# --- socials CRUD ---

def _social_row(row) -> dict:
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


@router.get("/admin/socials")
def admin_list_socials(_user: dict = Depends(auth.require_admin)) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source, external_id, author_name, author_handle, author_avatar_path, "
                "       content, media_path, external_url, posted_at, fetched_at, featured, hidden "
                "FROM social_posts ORDER BY COALESCE(posted_at, fetched_at) DESC"
            )
        ).all()
    return [_social_row(r) for r in rows]


@router.post("/admin/socials", status_code=201)
def admin_create_social(payload: SocialAdminUpsert, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM social_posts WHERE source = :s AND external_id = :e"),
            {"s": payload.source, "e": payload.external_id},
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="social post already exists")
        result = conn.execute(
            text(
                "INSERT INTO social_posts (source, external_id, author_name, author_handle, "
                "  content, external_url, posted_at, media_path, featured, hidden) "
                "VALUES (:source, :external_id, :author_name, :author_handle, :content, "
                "  :external_url, :posted_at, :media_path, :featured, :hidden)"
            ),
            {
                "source": payload.source,
                "external_id": payload.external_id,
                "author_name": payload.author_name,
                "author_handle": payload.author_handle,
                "content": payload.content,
                "external_url": payload.external_url,
                "posted_at": payload.posted_at,
                "media_path": payload.media_path,
                "featured": 1 if payload.featured else 0,
                "hidden": 1 if payload.hidden else 0,
            },
        )
        row = conn.execute(
            text(
                "SELECT id, source, external_id, author_name, author_handle, author_avatar_path, "
                "       content, media_path, external_url, posted_at, fetched_at, featured, hidden "
                "FROM social_posts WHERE id = :id"
            ),
            {"id": result.lastrowid},
        ).first()
        return _social_row(row)


@router.put("/admin/socials/{sid}")
def admin_update_social(
    sid: int,
    payload: SocialAdminUpsert,
    _user: dict = Depends(auth.require_admin),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    sets = []
    params: dict = {"id": sid}
    for col in (
        "source",
        "external_id",
        "author_name",
        "author_handle",
        "content",
        "external_url",
        "posted_at",
        "media_path",
    ):
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = data[col]
    for col in ("featured", "hidden"):
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = 1 if data[col] else 0
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sql = "UPDATE social_posts SET " + ", ".join(sets) + " WHERE id = :id"
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="social post not found")
        row = conn.execute(
            text(
                "SELECT id, source, external_id, author_name, author_handle, author_avatar_path, "
                "       content, media_path, external_url, posted_at, fetched_at, featured, hidden "
                "FROM social_posts WHERE id = :id"
            ),
            {"id": sid},
        ).first()
        return _social_row(row)


@router.delete("/admin/socials/{sid}")
def admin_delete_social(sid: int, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM social_posts WHERE id = :id"), {"id": sid})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="social post not found")
    return {"ok": True}


@router.post("/admin/socials/{sid}/approve")
def admin_approve_social(sid: int, _user: dict = Depends(auth.require_admin)) -> dict:
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE social_posts SET hidden = 0 WHERE id = :id"), {"id": sid}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="social post not found")
        row = conn.execute(
            text(
                "SELECT id, source, external_id, author_name, author_handle, author_avatar_path, "
                "       content, media_path, external_url, posted_at, fetched_at, featured, hidden "
                "FROM social_posts WHERE id = :id"
            ),
            {"id": sid},
        ).first()
        loaded = _social_row(row)
    notify_bot(
        "approved",
        {
            "entity": "social",
            "id": loaded["id"],
            "source": loaded["source"],
            "external_url": loaded["external_url"],
            "author_name": loaded["author_name"],
            "url_path": "/socials",
        },
    )
    return loaded


@router.post("/admin/socials/{sid}/reject")
def admin_reject_social(sid: int, _user: dict = Depends(auth.require_admin)) -> dict:
    """Reject = delete. Mirrors the existing admin_delete_social, but keeps a
    parallel name to the other entities for the bot's command surface."""
    return admin_delete_social(sid, _user)


@router.get("/admin/scraper-status")
def admin_scraper_status(_user: dict = Depends(auth.require_admin)) -> list[dict]:
    """Return one row per scraper from the scraper_status table."""
    from .. import scraper_status
    return scraper_status.all_states()


@router.post("/admin/scrapers/{name}/run-once")
def admin_run_scraper(name: str, _user: dict = Depends(auth.require_admin)) -> dict:
    """Trigger one scraper synchronously, outside the regular schedule.
    Returns the scraper's run() summary. Used by the 'Run Now' button in
    the admin panel."""
    from .. import scheduling
    if name not in scheduling.known_scrapers():
        raise HTTPException(status_code=404, detail=f"unknown scraper: {name}")
    try:
        result = scheduling.run_scraper_now(name)
    except Exception as exc:  # noqa: BLE001 — surface the error to the admin UI
        raise HTTPException(status_code=500, detail=f"scraper run failed: {exc}")
    return result

"""Public meetups endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import engine
from ..notifications import notify_bot
from ..schemas import MeetupSubmission
from ..utils import slugify

router = APIRouter()


def _row(row) -> dict:
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
    }


@router.get("/meetups")
def list_meetups(region: Optional[str] = Query(default=None)) -> list[dict]:
    sql = (
        "SELECT id, title, region, location, latitude, longitude, starts_at, "
        "       description, organizer_name, contact_url, approved "
        "FROM meetups WHERE approved = 1"
    )
    params: dict = {}
    if region and region != "all":
        sql += " AND region = :region"
        params["region"] = region
    sql += " ORDER BY starts_at ASC"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).all()
    return [_row(r) for r in rows]


@router.post("/submissions/meetups", status_code=201)
def submit_meetup(payload: MeetupSubmission) -> dict:
    mid = slugify(payload.title)
    with engine.begin() as conn:
        suffix = 1
        unique = mid
        while conn.execute(text("SELECT 1 FROM meetups WHERE id = :id"), {"id": unique}).first():
            suffix += 1
            unique = f"{mid}-{suffix}"
        conn.execute(
            text(
                "INSERT INTO meetups (id, title, region, location, latitude, longitude, "
                "  starts_at, description, organizer_name, contact_url, approved) "
                "VALUES (:id, :title, :region, :location, :latitude, :longitude, "
                "  :starts_at, :description, :organizer_name, :contact_url, 0)"
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
            },
        )
    notify_bot(
        "submission",
        {
            "entity": "meetup",
            "id": unique,
            "title": payload.title,
            "region": payload.region,
            "location": payload.location,
        },
    )
    return {"id": unique, "approved": False}

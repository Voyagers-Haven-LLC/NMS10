"""Pydantic request/response shapes.

These cover incoming submission payloads, login bodies, and admin edit forms.
Public response shapes are built as plain dicts in routers (not modeled here)
to keep server-side formatting flexible."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# --- bases ---

class BaseSubmission(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    builder_name: str = Field(min_length=1, max_length=100)
    builder_affiliation: Optional[str] = None
    description: Optional[str] = None
    builder_notes: Optional[str] = None
    platform: Optional[str] = Field(default=None, pattern="^(pc|ps|xbox|switch)$")
    galaxy: Optional[str] = None
    region: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")
    portal_address: Optional[str] = None
    tags: Optional[list[str]] = None
    submitter_email: Optional[str] = None
    submitter_discord_id: Optional[str] = None

    model_config = {"populate_by_name": True}


class BaseAdminUpsert(BaseModel):
    """Admin upsert — all fields optional so the same model serves PUT (partial)
    and POST (require title + builder_name validated in the route)."""
    id: Optional[str] = None
    title: Optional[str] = None
    builder_name: Optional[str] = None
    builder_affiliation: Optional[str] = None
    description: Optional[str] = None
    builder_notes: Optional[str] = None
    platform: Optional[str] = Field(default=None, pattern="^(pc|ps|xbox|switch)$")
    galaxy: Optional[str] = None
    region: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")
    portal_address: Optional[str] = None
    tags: Optional[list[str]] = None
    submitter_email: Optional[str] = None
    submitter_discord_id: Optional[str] = None
    star_count: Optional[int] = None
    view_count: Optional[int] = None
    hero_image_path: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(pending|approved|rejected)$")

    model_config = {"populate_by_name": True}


# --- communities ---

class CommunitySubmission(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    language: Optional[str] = None
    description: Optional[str] = None
    link_url: Optional[str] = None


class CommunityAdminUpsert(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    link_url: Optional[str] = None
    approved: Optional[bool] = None


# --- meetups ---

class MeetupSubmission(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    region: Optional[str] = Field(default=None, pattern="^(europe|north-america|asia-pacific|south-america)$")
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: Optional[str] = None  # ISO string; we keep it free-form for v1
    description: Optional[str] = None
    organizer_name: Optional[str] = None
    contact_url: Optional[str] = None


class MeetupAdminUpsert(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    region: Optional[str] = Field(default=None, pattern="^(europe|north-america|asia-pacific|south-america)$")
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: Optional[str] = None
    description: Optional[str] = None
    organizer_name: Optional[str] = None
    contact_url: Optional[str] = None
    approved: Optional[bool] = None


# --- socials ---

class SocialUrlSubmission(BaseModel):
    """Public submission of a social URL. The bot's /submit-social slash
    command and the admin panel both POST to /api/submissions/socials.
    Backend fetches Open Graph metadata server-side."""
    url: str
    submitter_discord_id: Optional[str] = None
    submitter_name: Optional[str] = None
    note: Optional[str] = None


class SocialAdminUpsert(BaseModel):
    source: str = Field(pattern="^(twitter|bluesky|youtube|reddit|tiktok|discord)$")
    external_id: str
    author_name: Optional[str] = None
    author_handle: Optional[str] = None
    content: Optional[str] = None
    external_url: Optional[str] = None
    posted_at: Optional[str] = None
    media_path: Optional[str] = None
    featured: Optional[bool] = None
    hidden: Optional[bool] = None


# --- auth ---

class LoginPayload(BaseModel):
    username: str
    password: str

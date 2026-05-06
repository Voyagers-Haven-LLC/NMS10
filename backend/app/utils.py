"""Small helpers reused across routers."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Iterable

PALETTE = ("cyan", "gold", "purple", "dark")


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "item"


def builder_initials(name: str) -> str:
    if not name:
        return "??"
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def hero_color_for(value: str) -> str:
    """Pick one of the v9 placeholder gradient colors deterministically from id."""
    h = sum(ord(c) for c in value or "")
    return PALETTE[h % len(PALETTE)]


def format_count(n: int | None) -> str:
    if n is None:
        return "0"
    return f"{n:,}"


def format_stars(n: int | None) -> str:
    return f"★ {n or 0}"


def format_submitted(ts: str | datetime | None) -> str:
    if ts is None:
        return ""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    return ts.strftime("%b %d, %Y")


def split_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t for t in re.split(r"\s+", raw.strip()) if t]


def join_tags(tags: Iterable[str] | None) -> str:
    if not tags:
        return ""
    return " ".join(t.strip() for t in tags if t and t.strip())

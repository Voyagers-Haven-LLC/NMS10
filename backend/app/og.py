"""Tiny Open Graph fetcher used by /api/submissions/socials.

Pulls og:title, og:description, og:image, plus a best-guess source platform
from the URL hostname. Network is intentionally short-circuited (httpx with
3s timeout) so a slow upstream can't block the submission. Failures fall
back to URL-only metadata."""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("nms10.og")

USER_AGENT = "nms10-bot/0.1 (+https://github.com/Parker1920/nms10-site)"
TIMEOUT_SECONDS = 3.0


def detect_source(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "twitter.com" in host or host.endswith("x.com") or host == "x.com":
        return "twitter"
    if "bsky" in host:
        return "bluesky"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "reddit" in host:
        return "reddit"
    if "tiktok" in host:
        return "tiktok"
    if "discord" in host:
        return "discord"
    return "twitter"  # safe-ish default; admin can change before approving


def _meta(soup: BeautifulSoup, key: str, attr: str = "property") -> Optional[str]:
    tag = soup.find("meta", attrs={attr: key})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def fetch_og(url: str) -> dict:
    """Best-effort OG metadata for a pasted social URL. Always returns a dict;
    fields are None on miss."""
    out = {
        "url": url,
        "source": detect_source(url),
        "title": None,
        "description": None,
        "image": None,
        "site_name": None,
    }
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        ) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            logger.warning("OG fetch %s -> HTTP %s", url, resp.status_code)
            return out
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype:
            return out
        # Cap body size so we don't parse a 50MB page
        body = resp.text[: 256 * 1024]
        soup = BeautifulSoup(body, "html.parser")
        out["title"] = _meta(soup, "og:title") or _meta(soup, "twitter:title") or (
            soup.title.string.strip() if soup.title and soup.title.string else None
        )
        out["description"] = (
            _meta(soup, "og:description") or _meta(soup, "twitter:description") or _meta(soup, "description", attr="name")
        )
        out["image"] = _meta(soup, "og:image") or _meta(soup, "twitter:image")
        out["site_name"] = _meta(soup, "og:site_name")
    except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001 — best-effort
        logger.warning("OG fetch failed for %s: %s", url, exc)
    return out


def stable_external_id(url: str) -> str:
    """Pick a deterministic id for a pasted URL so re-submitting the same link
    de-duplicates. Strips query/fragment, lowers, takes the path."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    host = (parsed.hostname or "").lower().replace("www.", "")
    base = f"{host}/{path}" if path else host
    base = re.sub(r"[^a-zA-Z0-9/_.\-]+", "-", base).strip("-/")
    return base[:200] or "submission"

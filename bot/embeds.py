"""Discord embed builders for each notification type, styled to match v9
gold/cyan palette."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

GOLD = 0xF5B849
CYAN = 0x4AD6D9

SOURCE_COLORS = {
    "twitter": 0x1D9BF0,
    "bluesky": 0x0085FF,
    "youtube": 0xFF0000,
    "reddit": 0xFF4500,
    "discord": 0x5865F2,
    "tiktok": 0xFFFFFF,
}


def submission_embed(payload: dict) -> discord.Embed:
    entity = (payload.get("entity") or "submission").lower()
    title = payload.get("title") or payload.get("name") or "(untitled)"
    fields_by_entity = {
        "base": [
            ("Builder", payload.get("builder_name")),
            ("Platform", payload.get("platform")),
        ],
        "community": [("Language", payload.get("language"))],
        "meetup": [
            ("Region", payload.get("region")),
            ("Location", payload.get("location")),
        ],
        "social": [("Source", payload.get("source"))],
    }
    embed = discord.Embed(
        title=f"📥 New {entity} submitted",
        description=f"**{title}**",
        color=CYAN,
    )
    for label, value in fields_by_entity.get(entity, []):
        if value:
            embed.add_field(name=label, value=str(value), inline=True)
    if payload.get("submitter_discord_id"):
        embed.add_field(name="Submitter", value=f"<@{payload['submitter_discord_id']}>", inline=True)
    if payload.get("external_url"):
        embed.add_field(name="Link", value=payload["external_url"], inline=False)
    embed.set_footer(text=f"id: {payload.get('id', '?')} · pending moderation")
    return embed


def approved_embed(payload: dict, site_url: Optional[str] = None) -> discord.Embed:
    entity = (payload.get("entity") or "submission").lower()
    title = payload.get("title") or payload.get("name") or "(untitled)"
    embed = discord.Embed(
        title=f"✨ {entity.capitalize()} approved",
        description=f"**{title}** is now live on the site.",
        color=GOLD,
    )
    if entity == "base":
        if payload.get("builder_name"):
            embed.add_field(name="Builder", value=payload["builder_name"], inline=True)
        if payload.get("platform"):
            embed.add_field(name="Platform", value=payload["platform"], inline=True)
    elif entity == "meetup":
        if payload.get("location"):
            embed.add_field(name="Where", value=payload["location"], inline=True)
        if payload.get("region"):
            embed.add_field(name="Region", value=payload["region"], inline=True)
    elif entity == "social":
        if payload.get("source"):
            embed.add_field(name="Source", value=payload["source"], inline=True)
        if payload.get("external_url"):
            embed.add_field(name="Link", value=payload["external_url"], inline=False)
    if site_url and payload.get("url_path"):
        embed.url = f"{site_url.rstrip('/')}{payload['url_path']}"
    embed.set_footer(text=f"id: {payload.get('id', '?')}")
    return embed


def new_social_embed(payload: dict) -> discord.Embed:
    source = (payload.get("source") or "twitter").lower()
    color = SOURCE_COLORS.get(source, CYAN)
    title = f"📡 New #NMS10 post · {source}"
    embed = discord.Embed(
        title=title,
        description=(payload.get("content") or "")[:500],
        color=color,
        url=payload.get("external_url") or None,
    )
    if payload.get("author"):
        embed.set_author(name=payload["author"])
    embed.set_footer(text=f"id: {payload.get('id', '?')} · auto-scraped")
    return embed


SOURCE_ICON = {
    "twitter": "𝕏",
    "bluesky": "☁",
    "youtube": "▶",
    "reddit": "↗",
    "discord": "◆",
    "tiktok": "♪",
}


def _word_truncate(text: str, limit: int) -> str:
    """Trim at a word boundary so we don't end on 'univer' or 'everythi'."""
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return cut + "…"


def _time_ago(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        # Accept both 'Z' and '+00:00' suffixes
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - ts).total_seconds()
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 86400 * 30:
        return f"{int(delta // 86400)}d ago"
    return ts.strftime("%b %d")


def status_embed(data: dict, site_url: str | None = None) -> discord.Embed:
    cd = data["countdown"]

    # Description doubles as the headline + steam stat. Markdown link to the
    # site is in the title (clickable in Discord clients that support it).
    if cd["reached"]:
        headline = "🎂 **The anniversary has begun.** We're all here."
    else:
        headline = (
            f"**{cd['days']}d {cd['hours']:02d}h {cd['minutes']:02d}m {cd['seconds']:02d}s** · "
            f"target Aug 9 2026 · 18:00 UTC"
        )

    description_parts = [headline]
    if data.get("steam_count") is not None:
        description_parts.append(f"🛸 **{data['steam_count']:,}** Travelers in-game right now")
    if site_url:
        description_parts.append(f"[Open the site →]({site_url})")

    embed = discord.Embed(
        title="NMS10 · Expedition for the Dreamers",
        url=site_url or None,
        description="\n".join(description_parts),
        color=GOLD,
    )

    counts = data["counts"]
    counts_line = (
        f"🏛 **{counts['bases']}** bases  ·  "
        f"📍 **{counts['meetups']}** meetups  ·  "
        f"🪐 **{counts['communities']}** communities"
    )
    embed.add_field(name="​", value=counts_line, inline=False)

    socials = data.get("recent_socials") or []
    if socials:
        blocks = []
        for s in socials:
            icon = SOURCE_ICON.get(s["source"], "•")
            author = s.get("author_name") or s.get("author_handle") or "—"
            handle = s.get("author_handle")
            ago = _time_ago(s.get("posted_at") or s.get("fetched_at"))
            url = s.get("external_url")

            # Header: bold author with source icon, then handle (if different
            # from name) and relative time, dimmed.
            header = f"{icon} **{author}**"
            meta_bits = []
            if handle and handle != author:
                meta_bits.append(handle)
            if ago:
                meta_bits.append(ago)
            if meta_bits:
                header += "  ·  " + "  ·  ".join(meta_bits)

            # Body: blockquoted content. Discord renders > prefix even inside
            # embed values. Linked through to the source if we have a URL.
            preview = _word_truncate(s.get("content") or "", 140)
            if url:
                body = f"> [{preview}]({url})"
            else:
                body = f"> {preview}"

            blocks.append(f"{header}\n{body}")

        # Blank line between entries for visual separation
        embed.add_field(name="Latest signals", value="\n\n".join(blocks), inline=False)

    embed.set_footer(text="Built for the NMS10 collaborative · /submit-base · /submit-meetup · /submit-social")
    return embed

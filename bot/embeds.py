"""Discord embed builders for each notification type, styled to match v9
gold/cyan palette."""

from __future__ import annotations

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


def status_embed(data: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🛸 NMS10 Status",
        color=GOLD,
    )
    cd = data["countdown"]
    if cd["reached"]:
        embed.description = "🎂 The anniversary has begun. We're all here."
    else:
        embed.description = (
            f"**{cd['days']}d {cd['hours']:02d}h {cd['minutes']:02d}m {cd['seconds']:02d}s** "
            f"to August 9 2026 18:00 UTC"
        )
    if data.get("steam_count") is not None:
        embed.add_field(
            name="In game now",
            value=f"{data['steam_count']:,} Travelers (Steam)",
            inline=False,
        )
    counts = data["counts"]
    embed.add_field(name="Bases", value=str(counts["bases"]), inline=True)
    embed.add_field(name="Meetups", value=str(counts["meetups"]), inline=True)
    embed.add_field(name="Communities", value=str(counts["communities"]), inline=True)
    if data.get("recent_socials"):
        lines = []
        for s in data["recent_socials"]:
            preview = (s.get("content") or "").replace("\n", " ")[:80]
            lines.append(f"• `{s['source']}` {preview}")
        embed.add_field(name="Latest signals", value="\n".join(lines) or "—", inline=False)
    return embed

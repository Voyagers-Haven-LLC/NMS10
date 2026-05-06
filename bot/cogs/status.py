"""/nms10-status — countdown, Steam count, totals, latest signals."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .. import api_client, embeds

logger = logging.getLogger("nms10.bot.status")

TARGET_TS = datetime(2026, 8, 9, 18, 0, 0, tzinfo=timezone.utc)


def _countdown_now() -> dict:
    now = datetime.now(timezone.utc)
    diff = (TARGET_TS - now).total_seconds()
    if diff <= 0:
        return {"reached": True, "days": 0, "hours": 0, "minutes": 0, "seconds": 0}
    days, rem = divmod(int(diff), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return {"reached": False, "days": days, "hours": hours, "minutes": minutes, "seconds": seconds}


async def gather_status() -> dict:
    bases = []
    meetups = []
    communities = []
    socials = []
    steam = {}
    errors: list[str] = []
    try:
        bases = await api_client.list_bases()
    except api_client.BackendError as exc:
        errors.append(str(exc))
    try:
        meetups = await api_client.list_meetups()
    except api_client.BackendError as exc:
        errors.append(str(exc))
    try:
        communities = await api_client.list_communities()
    except api_client.BackendError as exc:
        errors.append(str(exc))
    try:
        socials = await api_client.list_socials()
    except api_client.BackendError as exc:
        errors.append(str(exc))
    try:
        steam = await api_client.steam_count() or {}
    except api_client.BackendError as exc:
        errors.append(str(exc))
    return {
        "countdown": _countdown_now(),
        "steam_count": steam.get("player_count"),
        "counts": {
            "bases": len(bases),
            "meetups": len(meetups),
            "communities": len(communities),
        },
        "recent_socials": socials[:3],
        "errors": errors,
    }


class Status(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="nms10-status", description="Countdown + live stats for the NMS10 anniversary")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)
        try:
            data = await gather_status()
        except Exception as exc:  # noqa: BLE001 — keep the bot stable
            logger.exception("status failed: %s", exc)
            await interaction.followup.send(f"⚠️ Couldn't reach the backend: {exc}")
            return
        if data.get("errors"):
            note = "\n".join(f"⚠️ {e}" for e in data["errors"][:3])
            await interaction.followup.send(content=note, embed=embeds.status_embed(data))
        else:
            await interaction.followup.send(embed=embeds.status_embed(data))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Status(bot))

"""/bot-reload — reload servers.yaml without restarting the bot.

Gated by NMS10_BOT_ADMINS (comma-separated user IDs in env)."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .. import app_config, server_config

logger = logging.getLogger("nms10.bot.admin")


class BotAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bot-reload", description="Reload server channel config (admin only)")
    async def reload(self, interaction: discord.Interaction):
        if not app_config.is_bot_admin(interaction.user.id):
            await interaction.response.send_message(
                "Not authorized.", ephemeral=True
            )
            return
        try:
            routes = server_config.load()
        except Exception as exc:  # noqa: BLE001
            await interaction.response.send_message(f"Reload failed: {exc}", ephemeral=True)
            return
        lines = [f"**{r.name}** (`{gid}`)" for gid, r in routes.items()]
        body = "\n".join(lines) if lines else "_(no servers configured)_"
        await interaction.response.send_message(
            f"🔁 Reloaded {len(routes)} server(s):\n{body}", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotAdmin(bot))

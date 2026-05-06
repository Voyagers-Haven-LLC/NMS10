"""NMS10 Discord bot entry point.

Two run modes:
- Default: connect to Discord, register slash commands, AND start the
  webhook listener on 127.0.0.1:9000.
- `--no-discord`: skip Discord login but still run the webhook (so a CI
  or local test harness can verify backend → bot pipeline without a token).

The bot can be invoked from anywhere, but `python -m bot.main` from the
repo root works best because it picks up the bot package's relative
imports cleanly.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from . import api_client, app_config, embeds, server_config, webhook

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nms10.bot")

INTENTS = discord.Intents.default()
# We don't need privileged intents — slash commands & webhook posts are enough.

bot = commands.Bot(command_prefix="!", intents=INTENTS, help_command=None)


async def _send_embed(channel_id: int, embed: discord.Embed) -> None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            logger.warning("could not resolve channel %s: %s", channel_id, exc)
            return
    try:
        await channel.send(embed=embed)
    except discord.HTTPException as exc:
        logger.warning("send to %s failed: %s", channel_id, exc)


async def dispatch(notification_type: str, payload: dict) -> None:
    """Webhook dispatch entry point. Builds the appropriate embed and fans
    out to all channels subscribed to this notification type."""
    if notification_type == "submission":
        embed = embeds.submission_embed(payload)
    elif notification_type == "approved":
        embed = embeds.approved_embed(payload)
    elif notification_type == "new_social":
        embed = embeds.new_social_embed(payload)
    else:
        logger.warning("unknown notification type: %s", notification_type)
        return

    channel_ids = server_config.channels_for(notification_type)
    if not channel_ids:
        logger.info("no channels configured for type=%s — drop", notification_type)
        return
    if not bot.is_ready():
        logger.warning("bot not ready, queuing dropped (%s, %d channels)",
                       notification_type, len(channel_ids))
        return
    await asyncio.gather(*(_send_embed(cid, embed) for cid in channel_ids), return_exceptions=True)


async def _load_extensions() -> None:
    for ext in ("bot.cogs.submissions", "bot.cogs.status", "bot.cogs.admin"):
        await bot.load_extension(ext)


@bot.event
async def on_ready() -> None:
    try:
        synced = await bot.tree.sync()
        logger.info("synced %d slash commands as %s", len(synced), bot.user)
    except discord.HTTPException as exc:
        logger.warning("slash sync failed: %s", exc)
    routes = server_config.all_routes()
    logger.info("connected: %s | routes=%d", bot.user, len(routes))


async def _run_webhook_only() -> None:
    """Mode for local verification: run the webhook receiver standalone,
    no Discord connection. dispatch() will warn-and-drop because bot.is_ready()
    is false, which is the desired behavior — we want to see the receiver
    accept the POST and log the dispatch attempt."""
    server_config.load()
    runner = await webhook.start(dispatch)
    logger.info("webhook-only mode running. Ctrl+C to exit.")
    try:
        # Sleep forever
        await asyncio.Event().wait()
    finally:
        if runner is not None:
            await runner.cleanup()


async def _run() -> None:
    server_config.load()
    await _load_extensions()
    runner = await webhook.start(dispatch)
    try:
        await bot.start(app_config.DISCORD_TOKEN)
    finally:
        if runner is not None:
            await runner.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="NMS10 Discord bot")
    parser.add_argument(
        "--no-discord",
        action="store_true",
        help="Run only the webhook listener; skip Discord login. Useful for local pipeline tests.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Load extensions, dump command tree, and exit. No network at all.",
    )
    args = parser.parse_args()

    if args.validate:
        async def _validate():
            await _load_extensions()
            cmds = sorted(c.name for c in bot.tree.get_commands())
            print("Loaded slash commands:", cmds)
        asyncio.run(_validate())
        return 0

    if args.no_discord:
        try:
            asyncio.run(_run_webhook_only())
        except KeyboardInterrupt:
            return 0
        return 0

    if not app_config.DISCORD_TOKEN:
        # In containerized deploys (compose, Pi) we don't want a missing
        # token to crash-loop the container. Fall back to webhook-only mode
        # so the backend->bot pipeline still works for notifications and
        # health checks. Discord login becomes opt-in: drop the token in
        # the env file and restart the container.
        logger.warning(
            "NMS10_DISCORD_BOT_TOKEN is not set — running in webhook-only "
            "mode. Set the env var and restart to enable Discord features."
        )
        try:
            asyncio.run(_run_webhook_only())
        except KeyboardInterrupt:
            return 0
        return 0
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

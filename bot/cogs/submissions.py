"""Slash commands for public submissions: bases, communities, meetups, socials.

Each opens a Discord modal, validates client-side, then POSTs to the backend.
On success the user gets an ephemeral confirmation; on failure they see the
backend error so they can retry. Backend simultaneously fires notify_bot,
which posts a richer embed in the configured submission channels."""

from __future__ import annotations

import logging
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import api_client

logger = logging.getLogger("nms10.bot.submissions")


class BaseModal(discord.ui.Modal, title="Submit a base"):
    base_title = discord.ui.TextInput(label="Title", max_length=120, required=True)
    builder_name = discord.ui.TextInput(label="Builder name", max_length=80, required=True)
    galaxy_portal = discord.ui.TextInput(
        label="Galaxy & portal address",
        placeholder="Euclid · 10A8 F8AC 1023 0001",
        max_length=120,
        required=False,
    )
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )
    notes = discord.ui.TextInput(
        label="Builder's notes (optional)",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    def __init__(self, platform: str):
        super().__init__()
        self.platform = platform

    async def on_submit(self, interaction: discord.Interaction):
        galaxy, portal = "", ""
        if self.galaxy_portal.value:
            parts = re.split(r"[·|]", self.galaxy_portal.value, maxsplit=1)
            galaxy = parts[0].strip()
            portal = parts[1].strip() if len(parts) > 1 else ""
        body = {
            "title": self.base_title.value.strip(),
            "builder_name": self.builder_name.value.strip(),
            "platform": self.platform,
            "galaxy": galaxy or None,
            "portal_address": portal or None,
            "description": self.description.value or None,
            "builder_notes": self.notes.value or None,
            "submitter_discord_id": str(interaction.user.id),
        }
        try:
            res = await api_client.submit_base(body)
            await interaction.response.send_message(
                f"✅ Submitted **{body['title']}** as `{res['id']}`. Pending moderation.",
                ephemeral=True,
            )
        except api_client.BackendError as exc:
            await interaction.response.send_message(
                f"❌ Couldn't submit: {exc}", ephemeral=True
            )


class CommunityModal(discord.ui.Modal, title="Submit a community"):
    name = discord.ui.TextInput(label="Community name", max_length=120, required=True)
    language = discord.ui.TextInput(label="Language", max_length=40, required=False, placeholder="English")
    link_url = discord.ui.TextInput(label="Link URL", max_length=300, required=False, placeholder="https://")
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        body = {
            "name": self.name.value.strip(),
            "language": self.language.value or None,
            "link_url": self.link_url.value or None,
            "description": self.description.value or None,
        }
        try:
            res = await api_client.submit_community(body)
            await interaction.response.send_message(
                f"✅ Submitted **{body['name']}** as `{res['id']}`. Pending moderation.",
                ephemeral=True,
            )
        except api_client.BackendError as exc:
            await interaction.response.send_message(f"❌ Couldn't submit: {exc}", ephemeral=True)


class MeetupModal(discord.ui.Modal, title="Submit a meetup"):
    meetup_title = discord.ui.TextInput(label="Title", max_length=120, required=True)
    location = discord.ui.TextInput(label="Location (city, country)", max_length=120, required=True)
    coords = discord.ui.TextInput(
        label="Latitude, Longitude",
        placeholder="51.5074, -0.1278",
        max_length=60,
        required=False,
    )
    starts_at = discord.ui.TextInput(
        label="Starts at (ISO timestamp)",
        placeholder="2026-08-09T18:00:00Z",
        max_length=40,
        required=False,
    )
    description = discord.ui.TextInput(
        label="Description / contact URL",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    def __init__(self, region: str):
        super().__init__()
        self.region = region

    async def on_submit(self, interaction: discord.Interaction):
        lat, lng = None, None
        if self.coords.value:
            try:
                parts = [p.strip() for p in self.coords.value.split(",")]
                if len(parts) >= 2:
                    lat = float(parts[0])
                    lng = float(parts[1])
            except ValueError:
                await interaction.response.send_message(
                    "❌ Couldn't parse coordinates. Expected `lat, lng`.", ephemeral=True
                )
                return
        body = {
            "title": self.meetup_title.value.strip(),
            "region": self.region,
            "location": self.location.value.strip(),
            "latitude": lat,
            "longitude": lng,
            "starts_at": self.starts_at.value or None,
            "description": self.description.value or None,
        }
        try:
            res = await api_client.submit_meetup(body)
            await interaction.response.send_message(
                f"✅ Submitted **{body['title']}** as `{res['id']}`. Pending moderation.",
                ephemeral=True,
            )
        except api_client.BackendError as exc:
            await interaction.response.send_message(f"❌ Couldn't submit: {exc}", ephemeral=True)


class SocialModal(discord.ui.Modal, title="Submit a social link"):
    url = discord.ui.TextInput(
        label="Public URL",
        placeholder="https://x.com/... or https://bsky.app/...",
        max_length=400,
        required=True,
    )
    note = discord.ui.TextInput(
        label="Note (optional)",
        style=discord.TextStyle.paragraph,
        max_length=400,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        body = {
            "url": self.url.value.strip(),
            "submitter_discord_id": str(interaction.user.id),
            "submitter_name": interaction.user.display_name,
            "note": self.note.value or None,
        }
        try:
            res = await api_client.submit_social(body)
            if res.get("duplicate"):
                msg = f"ℹ️ Already submitted earlier (id `{res['id']}`)."
            else:
                msg = (
                    f"✅ Got it. Source detected: **{res['source']}**. "
                    f"id `{res['id']}`. Queued for moderation."
                )
            await interaction.response.send_message(msg, ephemeral=True)
        except api_client.BackendError as exc:
            await interaction.response.send_message(f"❌ Couldn't submit: {exc}", ephemeral=True)


PLATFORM_CHOICES = [
    app_commands.Choice(name="PC", value="pc"),
    app_commands.Choice(name="PlayStation", value="ps"),
    app_commands.Choice(name="Xbox", value="xbox"),
    app_commands.Choice(name="Switch", value="switch"),
]
REGION_CHOICES = [
    app_commands.Choice(name="Europe", value="europe"),
    app_commands.Choice(name="North America", value="north-america"),
    app_commands.Choice(name="Asia-Pacific", value="asia-pacific"),
    app_commands.Choice(name="South America", value="south-america"),
]


class Submissions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="submit-base", description="Submit a base for the NMS10 site")
    @app_commands.choices(platform=PLATFORM_CHOICES)
    async def submit_base(self, interaction: discord.Interaction, platform: app_commands.Choice[str]):
        await interaction.response.send_modal(BaseModal(platform=platform.value))

    @app_commands.command(name="submit-community", description="Submit a community for the NMS10 site")
    async def submit_community(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CommunityModal())

    @app_commands.command(name="submit-meetup", description="Submit an IRL meetup for the NMS10 site")
    @app_commands.choices(region=REGION_CHOICES)
    async def submit_meetup(self, interaction: discord.Interaction, region: app_commands.Choice[str]):
        await interaction.response.send_modal(MeetupModal(region=region.value))

    @app_commands.command(name="submit-social", description="Submit a social media link about NMS10")
    async def submit_social(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SocialModal())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Submissions(bot))

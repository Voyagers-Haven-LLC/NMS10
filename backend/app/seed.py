"""Idempotent seed: populates the v9 sample data on first DB creation.

Runs once at startup. Skips if the bases table already has rows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from .db import engine
from .utils import join_tags

logger = logging.getLogger("nms10.seed")


BASES = [
    {
        "id": "glass-atlas",
        "title": "The Glass Atlas",
        "builder_name": "Stars",
        "builder_affiliation": "Voyager's Haven",
        "description": (
            "A floating glass observatory perched above a class-A storm world. "
            "Built around a recovered Atlas Interface, the structure uses transparent "
            "paneling on every wall, so the storms below are visible from any room."
        ),
        "builder_notes": (
            "Started this build in March after finding the storm world by accident. "
            "The Atlas Interface was in a system three hops away — I rebuilt around it "
            "instead of moving it. Took about six weeks total."
        ),
        "platform": "pc",
        "galaxy": "Euclid",
        "region": "Iousongola",
        "portal_address": "10A8 · F8AC · 1023 · 0001",
        "tags": ["megabase", "floating", "monument"],
        "submitted_at": "2026-04-12T12:00:00Z",
        "star_count": 142,
        "view_count": 1847,
    },
    {
        "id": "tethys-reach",
        "title": "Tethys Reach",
        "builder_name": "Lyra Vesalius",
        "builder_affiliation": "Galactic Hub",
        "description": (
            "A bioluminescent deep-ocean colony spanning three coral spires. "
            "Built entirely underwater. Visit at night to see the full effect."
        ),
        "builder_notes": (
            "Underwater building is brutal. Every piece has to be placed against "
            "current and the camera fights you constantly. I made peace with imperfect "
            "alignments and leaned into the organic feel."
        ),
        "platform": "ps",
        "galaxy": "Eissentam",
        "region": "Hesepar Adjunct",
        "portal_address": "0FA8 · 1234 · ABCD · 0042",
        "tags": ["underwater", "settlement"],
        "submitted_at": "2026-03-30T12:00:00Z",
        "star_count": 98,
        "view_count": 1203,
    },
    {
        "id": "decadal-spire",
        "title": "Decadal Spire",
        "builder_name": "Watcher",
        "builder_affiliation": "Voyager's Haven",
        "description": (
            "Ten interconnected towers, one for each year of the journey. Every tower "
            "contains a different scene — launch, foundation, NEXT, BEYOND, and so on "
            "through Worlds II."
        ),
        "builder_notes": (
            "I wanted this to feel like a museum. Each tower has its own internal lighting "
            "and color tone matching the era it represents."
        ),
        "platform": "pc",
        "galaxy": "Hilbert",
        "region": "Ourgal Spur",
        "portal_address": "10A8 · 0010 · 0010 · 0010",
        "tags": ["themed", "monument", "megabase"],
        "submitted_at": "2026-04-01T12:00:00Z",
        "star_count": 211,
        "view_count": 3402,
    },
    {
        "id": "old-karst",
        "title": "Old Karst Settlement",
        "builder_name": "Tundra-7",
        "builder_affiliation": "Independent",
        "description": (
            "A frostbitten frontier outpost rebuilt in faithful 2016-era aesthetic. "
            "No Living Ship parts, no organic walls, no glass."
        ),
        "builder_notes": (
            "I gave myself a constraint: only use building parts that existed at launch. "
            "The result feels honest."
        ),
        "platform": "xbox",
        "galaxy": "Calypso",
        "region": "Frozen Reach",
        "portal_address": "20F8 · 7C0F · 0AB1 · 8821",
        "tags": ["settlement", "themed"],
        "submitted_at": "2026-03-22T12:00:00Z",
        "star_count": 64,
        "view_count": 742,
    },
    {
        "id": "ekimos-crossroads",
        "title": "Ekimo's Crossroads",
        "builder_name": "Ekimo",
        "builder_affiliation": "Voyager's Haven",
        "description": (
            "A modest waypoint built at the intersection of three exploration corridors. "
            "Open to all travelers."
        ),
        "builder_notes": (
            "I wanted something useful, not impressive. Every traveler who passes through "
            "can use the refiners and the trade terminal."
        ),
        "platform": "pc",
        "galaxy": "Euclid",
        "region": "Yileka Adjunct",
        "portal_address": "10A8 · 1234 · 5678 · 9ABC",
        "tags": ["outpost"],
        "submitted_at": "2026-04-05T12:00:00Z",
        "star_count": 89,
        "view_count": 1156,
    },
    {
        "id": "cartographers-library",
        "title": "The Cartographer's Library",
        "builder_name": "Jaina",
        "builder_affiliation": "Had.Sh",
        "description": (
            "An open archive of portal addresses, displayed as a physical library. "
            "Every wing represents a galaxy."
        ),
        "builder_notes": (
            "This is the build I am proudest of. As of submission day there are 412 "
            "addresses on the shelves."
        ),
        "platform": "ps",
        "galaxy": "Eissentam",
        "region": "Eyfert Khannate",
        "portal_address": "0FA8 · ABCD · 1234 · 5678",
        "tags": ["megabase", "themed"],
        "submitted_at": "2026-04-08T12:00:00Z",
        "star_count": 187,
        "view_count": 2891,
    },
]

COMMUNITIES = [
    {
        "id": "voyagers-haven",
        "name": "Voyager's Haven",
        "language": "English",
        "description": "A community atlas and mapping initiative for No Man's Sky exploration.",
        "link_url": "https://havenmap.online",
    },
    {
        "id": "galactic-hub",
        "name": "Galactic Hub",
        "language": "English",
        "description": "The largest civilization in No Man's Sky, established in Euclid since 2017.",
        "link_url": None,
    },
    {
        "id": "had-sh",
        "name": "Had.Sh",
        "language": "English / French",
        "description": "Cross-platform exploration community focused on portal address sharing.",
        "link_url": None,
    },
    {
        "id": "la-checktitude",
        "name": "la Checktitude [NMSF]",
        "language": "Français",
        "description": "French-speaking community organizing the 10 Years Expedition.",
        "link_url": None,
    },
    {
        "id": "alliance-of-galactic-travellers",
        "name": "Alliance of Galactic Travellers",
        "language": "English",
        "description": "Multi-platform alliance gathering Travelers from every galaxy and platform.",
        "link_url": None,
    },
    {
        "id": "placeholder-community",
        "name": "[Placeholder]",
        "language": "More to come",
        "description": "The community list will grow as more groups join the celebration.",
        "link_url": None,
    },
]

MEETUPS = [
    {
        "id": "london-2026",
        "title": "London IRL Meetup",
        "region": "europe",
        "location": "London, UK",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "starts_at": "2026-08-09T17:00:00Z",
        "description": "Pub gathering during the global synchronized moment. All Travelers welcome.",
    },
    {
        "id": "paris-2026",
        "title": "Paris Rendezvous",
        "region": "europe",
        "location": "Paris, France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "la Checktitude organizing a French-speaking community meetup with stream party.",
    },
    {
        "id": "berlin-2026",
        "title": "Berlin Travelers",
        "region": "europe",
        "location": "Berlin, Germany",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Gaming café gathering. BYOC if you can; otherwise come watch and celebrate.",
    },
    {
        "id": "nyc-2026",
        "title": "NYC Anniversary",
        "region": "north-america",
        "location": "New York City, USA",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Open meetup at a Manhattan venue. Look for the NMS10 banner.",
    },
    {
        "id": "la-2026",
        "title": "Los Angeles Gathering",
        "region": "north-america",
        "location": "Los Angeles, USA",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "West Coast meetup with co-op play and a community photo at 18:00 UTC sharp.",
    },
    {
        "id": "toronto-2026",
        "title": "Toronto Travelers",
        "region": "north-america",
        "location": "Toronto, Canada",
        "latitude": 43.6532,
        "longitude": -79.3832,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Casual meetup at a downtown gaming bar. Switch and PC players welcome.",
    },
    {
        "id": "tokyo-2026",
        "title": "Tokyo Synchronized",
        "region": "asia-pacific",
        "location": "Tokyo, Japan",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Late-night gathering for the synchronized moment (yes, it is 3 AM, bring snacks).",
    },
    {
        "id": "sydney-2026",
        "title": "Sydney Travelers",
        "region": "asia-pacific",
        "location": "Sydney, Australia",
        "latitude": -33.8688,
        "longitude": 151.2093,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Pre-dawn LAN party. We will sleep when we are dead, fellow Travelers.",
    },
    {
        "id": "sao-paulo-2026",
        "title": "São Paulo Encontro",
        "region": "south-america",
        "location": "São Paulo, Brazil",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "starts_at": "2026-08-09T18:00:00Z",
        "description": "Portuguese-speaking community gathering. Open to all Travelers in Brazil.",
    },
]

SOCIALS = [
    {
        "source": "twitter",
        "external_id": "seed-hg-1",
        "author_name": "Hello Games",
        "author_handle": "@hellogames",
        "content": "Ten years ago today, we launched a small game about exploring an infinite universe. Thank you for travelling with us. The journey is far from over. 🛸 #NMS10",
        "external_url": "https://twitter.com/hellogames",
        "posted_at": "2026-04-12T16:00:00Z",
        "featured": True,
    },
    {
        "source": "youtube",
        "external_id": "seed-yt-1",
        "author_name": "SpaceTraveler_42",
        "author_handle": "@spacetraveler42",
        "content": "NEW VIDEO: I rebuilt my first NMS base — the one I made in 2016 — using everything I've learned in 10 years of building. #NMS10",
        "external_url": "https://youtube.com",
        "posted_at": "2026-04-12T13:00:00Z",
        "featured": True,
    },
    {
        "source": "bluesky",
        "external_id": "seed-bsky-1",
        "author_name": "Explorer Lyra",
        "author_handle": "@lyra.bsky.social",
        "content": "Just hit 1,000 hours in NMS this week, and somehow my sense of wonder hasn't dulled. Here's to the next decade. 🌌 #NMS10",
        "external_url": "https://bsky.app",
        "posted_at": "2026-04-12T10:00:00Z",
        "featured": True,
    },
    {
        "source": "reddit",
        "external_id": "seed-reddit-1",
        "author_name": "u/atlas_seeker",
        "author_handle": "r/NoMansSkyTheGame",
        "content": "[GUIDE] Coordinating a multi-community 10th anniversary expedition. #NMS10",
        "external_url": "https://reddit.com/r/NoMansSkyTheGame",
        "posted_at": "2026-04-11T18:00:00Z",
        "featured": True,
    },
    {
        "source": "discord",
        "external_id": "seed-discord-1",
        "author_name": "Voyager's Haven",
        "author_handle": "#nms10-announcements",
        "content": "📣 Submission window for anniversary bases closes August 1. We're at 147 builds and counting. Get yours in. #NMS10",
        "external_url": "https://discord.gg",
        "posted_at": "2026-04-11T15:00:00Z",
        "featured": True,
    },
    {
        "source": "tiktok",
        "external_id": "seed-tiktok-1",
        "author_name": "nmsbuilder",
        "author_handle": "@nmsbuilder",
        "content": "The settlement I've been building for 4 months is finally finished. POV: you're seeing it for the first time. #NMS10",
        "external_url": "https://tiktok.com",
        "posted_at": "2026-04-10T20:00:00Z",
        "featured": True,
    },
]


def run_seed() -> None:
    with engine.connect() as conn:
        bases_count = conn.execute(text("SELECT COUNT(*) FROM bases")).scalar() or 0
    if bases_count > 0:
        return  # idempotent — only seed when DB is fresh

    logger.info("Seeding NMS10 v9 sample data into empty database…")
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        for b in BASES:
            conn.execute(
                text(
                    "INSERT INTO bases (id, title, builder_name, builder_affiliation, "
                    "  description, builder_notes, platform, galaxy, region, "
                    "  portal_address, tags, submitted_at, approved_at, status, "
                    "  view_count, star_count) "
                    "VALUES (:id, :title, :builder_name, :builder_affiliation, "
                    "  :description, :builder_notes, :platform, :galaxy, :region, "
                    "  :portal_address, :tags, :submitted_at, :approved_at, 'approved', "
                    "  :view_count, :star_count)"
                ),
                {
                    "id": b["id"],
                    "title": b["title"],
                    "builder_name": b["builder_name"],
                    "builder_affiliation": b["builder_affiliation"],
                    "description": b["description"],
                    "builder_notes": b["builder_notes"],
                    "platform": b["platform"],
                    "galaxy": b["galaxy"],
                    "region": b["region"],
                    "portal_address": b["portal_address"],
                    "tags": join_tags(b["tags"]),
                    "submitted_at": b["submitted_at"],
                    "approved_at": now,
                    "view_count": b["view_count"],
                    "star_count": b["star_count"],
                },
            )

        for c in COMMUNITIES:
            conn.execute(
                text(
                    "INSERT INTO communities (id, name, language, description, link_url, "
                    "  added_at, approved) "
                    "VALUES (:id, :name, :language, :description, :link_url, :added_at, 1)"
                ),
                {**c, "added_at": now},
            )

        for m in MEETUPS:
            conn.execute(
                text(
                    "INSERT INTO meetups (id, title, region, location, latitude, longitude, "
                    "  starts_at, description, submitted_at, approved) "
                    "VALUES (:id, :title, :region, :location, :latitude, :longitude, "
                    "  :starts_at, :description, :submitted_at, 1)"
                ),
                {**m, "submitted_at": now},
            )

        for s in SOCIALS:
            conn.execute(
                text(
                    "INSERT INTO social_posts (source, external_id, author_name, author_handle, "
                    "  content, external_url, posted_at, fetched_at, featured, hidden) "
                    "VALUES (:source, :external_id, :author_name, :author_handle, "
                    "  :content, :external_url, :posted_at, :fetched_at, :featured, 0)"
                ),
                {
                    "source": s["source"],
                    "external_id": s["external_id"],
                    "author_name": s["author_name"],
                    "author_handle": s["author_handle"],
                    "content": s["content"],
                    "external_url": s["external_url"],
                    "posted_at": s["posted_at"],
                    "fetched_at": now,
                    "featured": 1 if s.get("featured") else 0,
                },
            )
    logger.info("Seed complete: %d bases, %d communities, %d meetups, %d socials.",
                len(BASES), len(COMMUNITIES), len(MEETUPS), len(SOCIALS))

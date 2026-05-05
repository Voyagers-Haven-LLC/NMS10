# Scrapers

Stubs for the social-aggregation scrapers. Each platform = one Python module. APScheduler in the backend will load and schedule them. All scraped posts write to the `social_posts` table with `(source, external_id)` as the dedup key.

| Platform | Schedule | Method | Status |
|---|---|---|---|
| Bluesky | 5 min | Public AT Protocol API, no auth | stub |
| YouTube | 30 min | YouTube Data API v3, free key, search `#NMS10` | stub |
| Reddit | 10 min | Reddit OAuth (script app), search `#NMS10` in r/NoMansSkyTheGame | stub |
| Twitter | 30 min | Self-hosted Nitter + burner account session token | stub |
| Instagram | 30 min | Instaloader anonymous, hashtag query | stub |
| TikTok | manual | Discord bot — paste link in `#nms10-submissions` | stub |

Real implementations land in Phase 1.4.

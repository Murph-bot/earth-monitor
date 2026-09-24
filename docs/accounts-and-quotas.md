# Accounts, keys & free-tier inventory

Everything the system touches, what auth it needs, and its free-tier ceiling.
Verified 2026-09-25; sources in `docs/research/data-access-verification.md`.
Secrets live in env vars / `.env` (gitignored) — never committed.

## Data providers

| Service | Account needed | Auth mechanism | Free-tier limits | Cost risks |
|---|---|---|---|---|
| **Earth Search** (Element84) | None | Anonymous | STAC API free; `sentinel-2-c1-l2a` COGs in non-requester-pays bucket; `sentinel-1-grd` flagged requester-pays but **anonymous reads verified working (HTTP 206)** | None known. It's a gift — treat rate limits politely; cache searches |
| **Copernicus Data Space (CDSE)** | Yes — register at dataspace.copernicus.eu | OAuth2 password grant → access token (10 min lifetime, refresh 60 min) | 12 TB/mo transfer; 4 conns; ~5 STAC req/s; 50k direct-COG req/mo; 10k Sentinel Hub PU/mo | Throttled to 1 MB/s beyond quota — degrades, doesn't bill |
| **NASA Earthdata login** | Yes — urs.earthdata.nasa.gov | EDL username/password or app token | Covers VIIRS/HLS downloads + HyP3 job submission | HTTPS reads fine from anywhere; **direct S3 needs us-west-2 compute** — don't design around it |
| **ASF HyP3** | Uses Earthdata login | EDL | 8,000 credits/mo ≈ 1,600 RTC jobs @30 m, 533 @20 m, 133 @10 m | Products expire in 14 days → fetch & persist what we need; more credits = paid |
| **Planetary Computer** | None | Anonymous SAS token endpoint | No published hard quota (rate-limited); hosts `landsat-c2-l2` and `sentinel-1-rtc` | **SAS tokens may not be shared** → server-side reads only, signed hrefs never reach clients. Unmaintained — never sole path |
| **Google Earth Engine** | Optional, NOT in core path | GCP service account | Community tier: 150 EECU-h/mo | **Noncommercial-only.** Excluded per ADR-0001 (commercial entry = pay-as-you-go Limited plan if ever revisited) |

## Infrastructure (decisions land in later phases)

| Service | Used for | Free tier (verify at adoption) | Phase |
|---|---|---|---|
| GitHub Actions | CI (+ maybe scheduled ingestion) | ~2,000 min/mo private; unlimited public repos. **Cron auto-disables after 60 days of repo inactivity** and is ToS-gray as a general scheduler → prefer Workers cron for ingestion | 1, 4 |
| Neon **or** Supabase | Postgres+PostGIS | **Deferred — local Docker PostGIS per ADR-0002.** Candidates for Phase 10: Neon ~0.5 GB (Databricks-owned); Supabase 500 MB but pauses after ~1 week inactivity | 3, 10 |
| Cloudflare Pages | Web hosting | Unlimited sites/requests (Sotirios's existing account) | 7, 10 |
| Render / Cloudflare Workers | API + workers | Render free web services sleep; **Render free Postgres expires after 30 days** — never put the DB there. Fly.io free tier is dead (trial only); Railway "free" = $1/mo credit. Workers free: 100k req/day + **5 cron triggers** | 6, 10 |
| Cloudflare R2 | Thumbnails/derived rasters (if ever needed) | 10 GB, **zero egress fees** | 6+ |
| Resend / web-push | Email notifications | Resend free: 100 emails/day | 8 |
| Sentry | Error tracking | 5k errors/mo free | 10 |
| UptimeRobot / CF health checks | Uptime | 50 monitors free | 10 |

## Auth keys to provision (Phase 1 checklist)

- [ ] `CDSE_CLIENT_ID/SECRET` or user creds (CDSE account)
- [ ] `EARTHDATA_USER` + `EARTHDATA_PASSWORD` (or token)
- [ ] Database URL (per env: dev/test/prod)
- [ ] `API_SECRET_KEY` (JWT signing)
- [ ] `VAPID` keys (web push, Phase 8)
- [ ] `SENTRY_DSN` (Phase 10)

## Standing rules

1. Requester-pays endpoints are **banned by default** — an adapter must never
   emit an `s3://` or unsigned requester-pays URL without an explicit, reviewed
   decision. (Landsat `usgs-landsat` is the canonical trap.)
2. Every external call retries with exponential backoff and is logged with its
   quota class — quota exhaustion should show up in logs before it shows up as
   missing data.
3. Public deploys get rate limiting even in "private until stable" mode —
   open tile endpoints are how accidental bills happen.

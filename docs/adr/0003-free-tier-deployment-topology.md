# Free-tier deployment topology

Status: accepted (2026-09-25, Phase 9)

The $0-budget production topology splits every component onto the free tier
that fits its lifetime: **Neon** for Postgres (permanent free, PostGIS
included, scale-to-zero), **Render free web service** for the API, **Cloudflare
Pages** for the web build, and **GitHub Actions cron** for ingestion sweeps.

## Considered options

- **Render free Postgres** — rejected: deleted after 30 days. Neon's free tier
  is permanent; the catch (0.5 GB, compute suspends after 5 min idle) is fine
  for a metadata-only DB, and the pool now checks connections on checkout.
- **Fly.io / Railway** — rejected: Fly's free tier is dead (trial only),
  Railway's "free" is a $1/mo credit.
- **Render cron jobs for ingestion** — rejected: paid (~$1/mo). GH Actions cron
  is free on public repos and runs this repo's own pipeline — defensibly within
  the ToS clause restricting scheduled jobs to repo-related activity. Workers
  cron (5 free triggers) is the documented fallback if that reading changes.
- **TiTiler sidecar** — rejected earlier: in-process rio-tiler stays true.

## Consequences

- Render free web services **sleep on idle** — first request after a sleep is
  a slow cold start. Acceptable for a portfolio; documented in
  `docs/deployment.md`.
- Neon suspend drops idle connections — handled by pool checkout checks; cold
  starts add a few seconds to the first pooled connect.
- Two cron failure modes to remember: GH auto-disables schedules after 60 days
  of repo inactivity, and Neon suspends compute — both self-heal, neither
  loses data (watermark-based ingestion).
- `EM_ENVIRONMENT=prod` disables the dev-user auth fallback regardless of
  `EM_DEV_USER_EMAIL`.

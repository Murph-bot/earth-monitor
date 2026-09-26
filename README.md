# earth-monitor

A free, API-first Earth-surface monitoring product. Satellite imagery (Sentinel-2,
Landsat 8/9, Sentinel-1, VIIRS) is ingested on a schedule, reduced to metrics over
user-defined areas of interest, and served to thin clients (web now, native mobile
later) through one versioned API.

Working name — rename freely; the codebase must not depend on it.

## Status

**Phase 9 — deployable.** `render.yaml` blueprint (API), GH Actions cron
(ingestion), `VITE_API_URL` split-origin plumbing, prod auth hardening —
the human-side runbook is `docs/deployment.md` (Neon + Render + Pages).
Phase 8 added JWT auth, per-user AOIs, and alert rules → in-app
notifications; Phase 7 shipped the thin Vite/React/MapLibre client —
all live-verified on real Sentinel-2 data over Thessaly.
See `docs/` for the decision record, sensor matrix, and architecture.

## Dev quickstart

```sh
cd backend && uv sync && uv run uvicorn app.main:app --reload   # API on :8000
docker compose up --build                                       # PostGIS + API
npm install && npm run dev                                      # web on :5173
```

## Layout

```
/backend           Python + FastAPI, all business logic
/web               Thin web client
/mobile            Placeholder for a future Expo/React Native app
/packages/shared   Generated typed API client + design tokens
/infra             Docker, deployment config
/docs              Architecture, ADRs, research notes
```

## Docs

- `CONTEXT.md` — domain glossary (read first)
- `docs/architecture.md` — system design + diagram
- `docs/sensor-matrix.md` — data source comparison
- `docs/aoi-standard.md` — how areas of interest are represented
- `docs/accounts-and-quotas.md` — every external account and its free-tier limits
- `docs/deployment.md` — the $0 production topology runbook
- `docs/adr/` — why STAC-first, local Postgres, this free-tier topology
- `docs/research/` — verified source notes with citations

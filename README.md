# earth-monitor

A free, API-first Earth-surface monitoring product. Satellite imagery (Sentinel-2,
Landsat 8/9, Sentinel-1, VIIRS) is ingested on a schedule, reduced to metrics over
user-defined areas of interest, and served to thin clients (web now, native mobile
later) through one versioned API.

Working name — rename freely; the codebase must not depend on it.

## Status

**Phase 7 — web client.** Thin Vite/React/MapLibre frontend in `web/`:
AOI draw/list/delete, scene browser overlaying live COG tiles, NDVI/NDWI
charts — all through the generated client in `packages/shared`. Backend
(Phases 1–6): schema, scheduled ingestion, NDVI/NDWI analysis, `/v1` API +
dynamic tiles — all live on real Sentinel-2 data over Thessaly.
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
- `docs/adr/0001-*.md` — why data access is STAC-first multi-catalog
- `docs/research/` — verified source notes with citations

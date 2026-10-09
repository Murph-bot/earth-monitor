# earth-monitor

Monitors Earth's surface over user-defined areas: scheduled satellite observations become metric
time series, alerts and map tiles. API-first: all logic lives in `backend/`; `web/` and `mobile/`
are thin clients of `/v1`.

@CONTEXT.md

## Commands

- Backend (from `backend/`): `uv sync`, `uv run python -m app.db.migrate` (needs `docker compose up -d db`),
  `uv run uvicorn app.main:app --reload`, `uv run pytest`, `uv run ruff check .`,
  `uv run ruff format .`, `uv run mypy app`
- Web: `npm run dev` / `npm run build` from the repo root (npm workspaces: `web`, `packages/shared`)
- Shared client: `npm run gen:client` regenerates `packages/shared` from the backend OpenAPI schema

## Rules

- Use the glossary terms in `CONTEXT.md` (AOI, Scene, Sensor, Collection, ...) in code and docs,
  and avoid the listed alternatives.
- The API contract is generated: after changing any route or response model in `backend/app/api`,
  run `npm run gen:client` and commit `packages/shared/openapi.json` and `api-types.d.ts` together.
- Run `/verify` before reporting work done.

# backend

FastAPI + Postgres/PostGIS backend. All business logic lives here; clients are
thin consumers of the versioned `/v1` API.

## Dev

```sh
uv sync                  # install deps into .venv
uv run uvicorn app.main:app --reload
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy app          # typecheck
```

Or via Docker from the repo root: `docker compose up --build` (PostGIS + API).

## Layout

- `app/api/v1/` — versioned routers. New API versions get a new directory,
  never a breaking change inside `/v1`.
- `app/config.py` — pydantic-settings; all env config flows through `Settings`.
- `app/logging.py` — structlog setup; console in dev, JSON in prod.
- `app/adapters/` — sensor adapters (Phase 2).
- `app/modules/` — analysis modules (Phase 5).
- `app/ingestion/` — scheduled ingestion workers (Phase 4).
- `app/db/` — database layer (Phase 3).

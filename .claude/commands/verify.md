---
description: Run the earth-monitor gate (ruff, mypy, pytest, shared typecheck, web build)
allowed-tools: Bash(uv run *), Bash(npm run *), Bash(npm -w *), Bash(cd backend*)
---
Run in order and report each result; stop at the first failure:

1. `cd backend && uv run ruff check .`
2. `cd backend && uv run mypy app`
3. `cd backend && uv run pytest` (some tests need the database: `docker compose up -d db`; if they fail
   only for lack of it, say so)
4. `npm -w packages/shared run typecheck`
5. `npm run build`

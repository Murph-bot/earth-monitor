# web

Placeholder — built in Phase 7.

Thin client: renders maps, AOIs, dashboards. All logic comes from the `/v1`
API via the generated typed client in `packages/shared`. Nothing in this app
may talk to STAC catalogs or compute metrics.

## Ombria UI

UI text is "Ombria"; repo, packages, Pages project and domains keep the
`earth-monitor` names (rename pending a domain/trademark check).

- `VITE_API_URL` — API origin (split-origin deploys). Keep it in step with the
  `connect-src`/`img-src` origin in `public/_headers`.
- `VITE_TURNSTILE_SITE_KEY` — optional. Unset = no Turnstile widget. The API
  verifies tokens only when `EM_TURNSTILE_SECRET` is set.
- Client routes live in `src/router.tsx` and must each have an explicit line in
  `public/_redirects` (no catch-all: unknown paths must return HTTP 404).
- Pre-deploy checks: build, serve `dist` with `e2e/pages_server.py`, then run
  `e2e/flow.py` with `uv run --with playwright` (API mocked; covers
  draw-then-sign-up, waking, tap targets, 404).

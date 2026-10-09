---
description: Regenerate the shared API client from the backend OpenAPI schema and show the diff
allowed-tools: Bash(npm run gen:client), Bash(git diff *), Bash(git status *)
---
Run `npm run gen:client` (dumps OpenAPI from the backend, then regenerates `packages/shared`).
Then show `git status` and a summary of what changed in `packages/shared/openapi.json` and
`api-types.d.ts`. If nothing changed, say the contract is already in sync.

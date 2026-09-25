// Typed API client — types generated from the backend's OpenAPI spec.
// Regenerate: (cd backend && uv run python -m scripts.dump_openapi) && npm run gen
import createClient from "openapi-fetch";
import type { paths } from "./api-types";

export const api = (baseUrl: string) =>
  createClient<paths>({ baseUrl: baseUrl.replace(/\/$/, "") });

export type { components, paths } from "./api-types";

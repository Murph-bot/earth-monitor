import { api, type components } from "@earth-monitor/shared"

export type { components }

// Empty = same-origin (vite dev proxy forwards /v1 to uvicorn, and a
// same-origin prod deploy needs nothing). Split-origin prod (e.g. Cloudflare
// Pages + Render) sets VITE_API_URL at build time.
// Trailing slash stripped once: tile URLs are rewritten with API_BASE, and
// "//v1/..." matches no route.
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "")
export const client = api(API_BASE)

export type Aoi = components["schemas"]["AoiOut"]
export type AoiDetail = components["schemas"]["AoiDetail"]
export type SceneSummary = components["schemas"]["SceneSummary"]
export type MetricsResponse = components["schemas"]["MetricsResponse"]
export type MetricSeries = components["schemas"]["MetricSeries"]

export interface Health {
  status: string
  db: string
}

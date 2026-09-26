import { api, type components } from "@earth-monitor/shared"

export type { components }

// Empty = same-origin (vite dev proxy forwards /v1 to uvicorn, and a
// same-origin prod deploy needs nothing). Split-origin prod (e.g. Cloudflare
// Pages + Render) sets VITE_API_URL at build time.
export const API_BASE = import.meta.env.VITE_API_URL ?? ""
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

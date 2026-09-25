import { api, type components } from "@earth-monitor/shared"

export type { components }

// Same-origin — vite dev proxy forwards /v1 to uvicorn; prod serves it
// behind the same host, so the client never hardcodes a URL.
export const client = api("")

export type Aoi = components["schemas"]["AoiOut"]
export type AoiDetail = components["schemas"]["AoiDetail"]
export type SceneSummary = components["schemas"]["SceneSummary"]
export type MetricsResponse = components["schemas"]["MetricsResponse"]
export type MetricSeries = components["schemas"]["MetricSeries"]

export interface Health {
  status: string
  db: string
}

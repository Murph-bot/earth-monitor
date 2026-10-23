// Plain-language names for API metric names and rule operators. The API keeps
// its names (ndvi_mean, lt, ...); only the UI is renamed.
const METRICS: Record<string, { label: string; short: string; unit: string }> = {
  ndvi_mean: { label: "Greenness (NDVI)", short: "greenness", unit: "" },
  rain_mm: { label: "Rain (daily total)", short: "daily rain", unit: " mm" },
}

export const KNOWN_METRICS = Object.keys(METRICS)
export const metricLabel = (name: string) => METRICS[name]?.label ?? name
export const metricShort = (name: string) => METRICS[name]?.short ?? name
export const metricUnit = (name: string) => METRICS[name]?.unit ?? ""

export const OPS = ["lt", "lte", "gt", "gte"] as const
export type Op = (typeof OPS)[number]
export const opLabel = (op: string) =>
  ({ lt: "below", lte: "at or below", gt: "above", gte: "at or above" })[op] ?? op

/** "Tell me when North field's greenness drops below 0.25." */
export const ruleSentence = (area: string, metric: string, op: string, value: string) => {
  const verb = op === "lt" || op === "lte" ? "drops" : "rises"
  return `Tell me when ${area}'s ${metricShort(metric)} ${verb} ${opLabel(op)} ${value}${metricUnit(metric)}.`
}

export const km2 = (m2: number) => (m2 / 1e6).toFixed(1)

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" })

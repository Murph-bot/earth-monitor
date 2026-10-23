// Greece overview background — NASA GIBS WMTS (EPSG:3857, "best" endpoint).
// Verified against GetCapabilities 2026-10-23:
//   ResourceURL template .../{Layer}/default/{Time}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.png
//   VIIRS_NOAA20_NDVI_8Day / VIIRS_NOAA21_NDVI_8Day: image/png, GoogleMapsCompatible_Level8, P1D
//   IMERG_Precipitation_Rate_30min: image/png, GoogleMapsCompatible_Level6, PT30M
// TileRow = y, TileCol = x. Source maxzoom matches the matrix set so MapLibre
// overzooms the coarse tiles instead of requesting levels that 400.
// The latest time comes from WMTS DescribeDomains (a few hundred bytes, CORS *)
// so tile URLs carry an explicit date (GIBS sends no-store for time=default).
// No EOX layers anywhere: their imagery licence is non-commercial.

export const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"

export type OverviewKind = "greenness" | "rain"

export interface OverviewLayer {
  kind: OverviewKind
  layer: string
  matrixSet: string
  maxzoom: number
  time: string // ISO date / datetime, or "default" when the domain lookup failed
}

interface Candidate {
  layer: string
  matrixSet: string
  maxzoom: number
}

export const CANDIDATES: Record<OverviewKind, Candidate[]> = {
  greenness: [
    { layer: "VIIRS_NOAA20_NDVI_8Day", matrixSet: "GoogleMapsCompatible_Level8", maxzoom: 8 },
    { layer: "VIIRS_NOAA21_NDVI_8Day", matrixSet: "GoogleMapsCompatible_Level8", maxzoom: 8 },
  ],
  rain: [
    { layer: "IMERG_Precipitation_Rate_30min", matrixSet: "GoogleMapsCompatible_Level6", maxzoom: 6 },
  ],
}

// a primary layer whose newest date is older than this is treated as stalled
const STALE_DAYS = 20

export const tileUrl = (l: Pick<OverviewLayer, "layer" | "matrixSet" | "time">) =>
  `${GIBS}/${l.layer}/default/${l.time}/${l.matrixSet}/{z}/{y}/{x}.png`

export const describeDomainsUrl = (c: Candidate) =>
  `${GIBS}/wmts.cgi?SERVICE=WMTS&REQUEST=DescribeDomains&VERSION=1.0.0&LAYER=${c.layer}&TILEMATRIXSET=${c.matrixSet}`

/** Newest instant in a WMTS time domain, e.g.
 * "2025-09-22/2025-11-15/P1D,2025-11-17/2026-10-22/P1D" -> "2026-10-22". */
export const latestTime = (xml: string): string | null => {
  const m = /<Domain>([^<]+)<\/Domain>/.exec(xml)
  if (!m?.[1]) return null
  const last = m[1].trim().split(",").pop() ?? ""
  const parts = last.split("/")
  const end = (parts.length >= 2 ? parts[1] : parts[0])?.trim()
  return end && /^\d{4}-\d{2}-\d{2}/.test(end) ? end : null
}

const ageDays = (t: string, now: Date) => (now.getTime() - Date.parse(t)) / 86_400_000

export const resolveOverview = async (
  kind: OverviewKind,
  fetcher: typeof fetch = fetch,
  now: Date = new Date(),
): Promise<OverviewLayer> => {
  const cands = CANDIDATES[kind]
  for (const c of cands) {
    try {
      const r = await fetcher(describeDomainsUrl(c), { signal: AbortSignal.timeout(8000) })
      if (!r.ok) continue
      const t = latestTime(await r.text())
      if (!t) continue
      if (c !== cands[cands.length - 1] && ageDays(t, now) > STALE_DAYS) continue
      return { kind, ...c, time: t }
    } catch {
      // try the next candidate
    }
  }
  const first = cands[0]!
  return { kind, ...first, time: "default" }
}

/** "Greenness to Oct 22" / "Rain 05:30 UTC". */
export const dataDateLabel = (l: OverviewLayer): string => {
  if (l.time === "default") return l.kind === "rain" ? "Rain: latest" : "Greenness: latest"
  const d = new Date(l.time.length === 10 ? `${l.time}T00:00:00Z` : l.time)
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" })
  if (l.kind === "greenness") return `Greenness to ${day}`
  const hm = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Athens" })
  const dayAth = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/Athens" })
  return `Rain ${dayAth}, ${hm} Athens time`
}

const fmtDay = (d: Date) =>
  d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/Athens" })

/** Both layers on one line, Athens time:
 * "Greenness 15–22 Oct (8-day) · Rain 23 Oct, 08:30 Athens time". */
export const bothDatesLabel = (g: OverviewLayer | null, r: OverviewLayer | null): string => {
  let green = "Greenness: loading…"
  if (g) {
    if (g.time === "default") green = "Greenness: latest"
    else {
      const end = new Date(`${g.time.slice(0, 10)}T12:00:00Z`)
      const start = new Date(end.getTime() - 7 * 86_400_000)
      green = `Greenness ${fmtDay(start)}–${fmtDay(end)} (8-day)`
    }
  }
  const rain = r ? dataDateLabel(r) : "Rain: loading…"
  return `${green} · ${rain}`
}

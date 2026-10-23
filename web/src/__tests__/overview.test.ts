import { describe, expect, it } from "vitest"
import { CANDIDATES, dataDateLabel, describeDomainsUrl, latestTime, resolveOverview, tileUrl } from "../overview"

const domains = (d: string) =>
  `<Domains><DimensionDomain><ows:Identifier>time</ows:Identifier><Domain>${d}</Domain></DimensionDomain></Domains>`

const ok = (body: string) => Promise.resolve(new Response(body, { status: 200 }))

describe("GIBS overview", () => {
  it("builds the WMTS REST template as z/row(y)/col(x)", () => {
    expect(tileUrl({ layer: "VIIRS_NOAA20_NDVI_8Day", matrixSet: "GoogleMapsCompatible_Level8", time: "2026-10-22" })).toBe(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_NOAA20_NDVI_8Day/default/2026-10-22/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png",
    )
  })

  it("caps source maxzoom at the matrix set level", () => {
    expect(CANDIDATES.greenness.map((c) => c.maxzoom)).toEqual([8, 8])
    expect(CANDIDATES.rain[0]?.maxzoom).toBe(6)
    expect(CANDIDATES.rain[0]?.layer).toBe("IMERG_Precipitation_Rate_30min")
  })

  it("parses the newest instant from a multi-range domain", () => {
    expect(latestTime(domains("2025-09-22/2025-11-15/P1D,2025-11-17/2026-10-22/P1D"))).toBe("2026-10-22")
    expect(latestTime(domains("2026-02-11T09:00:00Z/2026-10-23T05:30:00Z/PT30M"))).toBe("2026-10-23T05:30:00Z")
    expect(latestTime("<x/>")).toBeNull()
  })

  it("uses NOAA-20 when fresh", async () => {
    const l = await resolveOverview("greenness", () => ok(domains("2025-11-17/2026-10-22/P1D")), new Date("2026-10-23"))
    expect(l.layer).toBe("VIIRS_NOAA20_NDVI_8Day")
    expect(l.time).toBe("2026-10-22")
  })

  it("falls back to NOAA-21 when NOAA-20 fails or is stale", async () => {
    const failing = (url: string | URL | Request) =>
      String(url).includes("NOAA20") ? Promise.resolve(new Response("", { status: 500 })) : ok(domains("2026-09-27/2026-10-22/P1D"))
    const a = await resolveOverview("greenness", failing as typeof fetch, new Date("2026-10-23"))
    expect(a.layer).toBe("VIIRS_NOAA21_NDVI_8Day")
    const stale = (url: string | URL | Request) =>
      ok(domains(String(url).includes("NOAA20") ? "2026-01-01/2026-08-01/P1D" : "2026-09-27/2026-10-22/P1D"))
    const b = await resolveOverview("greenness", stale as typeof fetch, new Date("2026-10-23"))
    expect(b.layer).toBe("VIIRS_NOAA21_NDVI_8Day")
  })

  it("degrades to time=default when GIBS domains are unreachable", async () => {
    const l = await resolveOverview("rain", () => Promise.reject(new Error("offline")))
    expect(l.time).toBe("default")
    expect(describeDomainsUrl(CANDIDATES.rain[0]!)).toContain("REQUEST=DescribeDomains")
  })

  it("labels the data date", () => {
    expect(dataDateLabel({ kind: "greenness", layer: "", matrixSet: "", maxzoom: 8, time: "2026-10-22" })).toBe("Greenness to 22 Oct")
    expect(dataDateLabel({ kind: "rain", layer: "", matrixSet: "", maxzoom: 6, time: "2026-10-23T05:30:00Z" })).toBe("Rain 23 Oct, 08:30 Athens time")
  })
})

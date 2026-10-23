import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { showRegionPanel } from "../regionPanel"
import { RegionSummaryPanel } from "../components/RegionSummaryPanel"

describe("showRegionPanel", () => {
  it("opens on landing and explore when a region is zoomed", () => {
    expect(showRegionPanel("landing", true, false)).toBe(true)
    expect(showRegionPanel("explore", true, false)).toBe(true)
  })
  it("stays closed after All Greece, while drawing, or on other routes", () => {
    expect(showRegionPanel("explore", false, false)).toBe(false)
    expect(showRegionPanel("explore", true, true)).toBe(false)
    expect(showRegionPanel("areas", true, false)).toBe(false)
  })
})

describe("RegionSummaryPanel", () => {
  it("renders the region figures", () => {
    const html = renderToStaticMarkup(
      <RegionSummaryPanel
        onClose={() => {}}
        state={{
          status: "ready",
          data: {
            region: "attica",
            name: "Attica",
            bounds: [23, 37, 24.5, 38.5],
            window_days: 7,
            clear_max_cloud_pct: 20,
            generated_at: "2026-10-23T12:00:00Z",
            greenness: { mean: 0.26, previous_mean: null, delta: null, areas: 2 },
            rain: { mean_mm: 0.76, areas: 2 },
            scenes: { clear: 2, cloudy: 2, latest_scene_at: "2026-10-21T09:00:00Z" },
          },
        }}
      />,
    )
    expect(html).toContain("Attica greenness")
    expect(html).toContain("0.26")
    expect(html).toContain("1 mm")
    expect(html).toContain("21 Oct 2026")
  })
})

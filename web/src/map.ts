import * as maplibregl from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url"
import { getToken } from "./auth"
import { tileUrl, type OverviewLayer } from "./overview"

// MapLibre 6 resolves its worker at runtime, which bundlers miss; ship it as an asset.
maplibregl.setWorkerUrl(workerUrl)

export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/dark"
export const BASEMAP_BG = "#0d1512"

// MapLibre, no token: OpenFreeMap dark basemap for orientation — scene imagery is
// the product layer rendered by our own /v1/tiles endpoints.
export const initMap = (container: HTMLElement) => {
  const map = new maplibregl.Map({
    container,
    // OpenFreeMap dark vector style (free, no key; tiles/glyphs/sprites all
    // on tiles.openfreemap.org). Background retinted to the app surface.
    style: BASEMAP_STYLE,
    bounds: GREECE_BOUNDS,
    fitBoundsOptions: { padding: viewPadding() },
    // attribution sits top-right (added below) so the phone bottom sheet
    // never covers it
    attributionControl: false,
    // keeps the WebGL buffer readable — headless screenshots & future
    // "export view as image" both need it; minor perf cost
    canvasContextAttributes: { preserveDrawingBuffer: true },
    // scene tiles are owner-scoped; MapLibre fetches them itself, outside
    // the API client's auth middleware
    transformRequest: (url) => {
      const t = getToken()
      return t && url.includes("/v1/tiles/")
        ? { url, headers: { Authorization: `Bearer ${t}` } }
        : { url }
    },
  })
  map.once("styledata", () => {
    for (const l of map.getStyle().layers ?? [])
      if (l.type === "background") map.setPaintProperty(l.id, "background-color", BASEMAP_BG)
  })
  // basemap style references sprite images it doesn't ship (circle-11,
  // wood-pattern…). MapLibre 6 fires `styleimagemissing` only *after* the
  // lookup failed and warns unconditionally, so a listener can't silence it;
  // the resolver runs first — register a transparent 1x1 there.
  map.setMissingStyleImageResolver((id) => {
    if (!map.hasImage(id)) map.addImage(id, { width: 1, height: 1, data: new Uint8Array(4) })
  })
  // phone: collapsed behind a 44px toggle; desktop: always expanded
  const phone = typeof window !== "undefined" && window.innerWidth <= PHONE_MAX
  map.addControl(
    new maplibregl.AttributionControl({
      compact: phone,
      customAttribution: "Contains modified Copernicus Sentinel data",
    }),
    "top-right",
  )
  if (phone)
    container
      .querySelector(".maplibregl-ctrl-attrib")
      ?.classList.remove("maplibregl-compact-show")
  return map
}

// All of Greece incl. Crete and the eastern Aegean (design brief §10)
export const GREECE_BOUNDS: [number, number, number, number] = [19, 34, 30, 42]
export const TEAL = "#14837d" // s5

const PHONE_MAX = 899
const PANEL_W = 380 // Sheet desk:w-[380px]
/** Keep fitted views clear of the phone bottom sheet + control block. */
export const viewPadding = (): maplibregl.PaddingOptions => {
  if (typeof window === "undefined" || window.innerWidth > PHONE_MAX)
    return { top: 24, right: 24, bottom: 24, left: PANEL_W + 16 + 24 } // panel (left-4 + 380px) + 24
  return { top: 16, right: 16, left: 16, bottom: Math.round(window.innerHeight * 0.32) + 150 }
}

export const fitBbox = (map: maplibregl.Map, b: readonly number[], animate = true) => {
  const [minx = 0, miny = 0, maxx = 0, maxy = 0] = b
  map.fitBounds(
    [
      [minx, miny],
      [maxx, maxy],
    ],
    { padding: viewPadding(), duration: animate ? 700 : 0 },
  )
}

export const OVERVIEW_OPACITY = 0.6
const OVERVIEW_SRC = "overview"

/** (Re)place the GIBS overview raster under the field layers. */
export const setOverview = (
  map: maplibregl.Map,
  layer: OverviewLayer | null,
  visible: boolean,
  beforeId?: string,
) => {
  if (map.getLayer(OVERVIEW_SRC)) map.removeLayer(OVERVIEW_SRC)
  if (map.getSource(OVERVIEW_SRC)) map.removeSource(OVERVIEW_SRC)
  if (!layer) return
  map.addSource(OVERVIEW_SRC, {
    type: "raster",
    tiles: [tileUrl(layer)],
    tileSize: 256,
    minzoom: 0,
    maxzoom: layer.maxzoom, // overzoom past the matrix set, never blank
    attribution:
      '<a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">Imagery: NASA GIBS</a>',
  })
  map.addLayer(
    {
      id: OVERVIEW_SRC,
      type: "raster",
      source: OVERVIEW_SRC,
      layout: { visibility: visible ? "visible" : "none" },
      paint: { "raster-opacity": OVERVIEW_OPACITY, "raster-resampling": "linear" },
    },
    beforeId && map.getLayer(beforeId) ? beforeId : undefined,
  )
}

export const regionFeatures = (
  regions: { slug: string; name: string; bounds: number[] }[],
): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: regions.map((r) => {
    const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = r.bounds
    return {
      type: "Feature",
      properties: { slug: r.slug, name: r.name },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1],
            [x0, y0],
          ],
        ],
      },
    }
  }),
})

export const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] }

export const rectFeature = (a: maplibregl.LngLat, b: maplibregl.LngLat): GeoJSON.Feature => {
  const minx = Math.min(a.lng, b.lng)
  const maxx = Math.max(a.lng, b.lng)
  const miny = Math.min(a.lat, b.lat)
  const maxy = Math.max(a.lat, b.lat)
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [minx, miny],
          [maxx, miny],
          [maxx, maxy],
          [minx, maxy],
          [minx, miny],
        ],
      ],
    },
  }
}

export const setGeoData = (map: maplibregl.Map, id: string, data: GeoJSON.GeoJSON) => {
  const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined
  src?.setData(data)
}

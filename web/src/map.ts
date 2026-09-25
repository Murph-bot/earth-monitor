import maplibregl from "maplibre-gl"

// MapLibre, no token: OSM raster basemap for orientation — scene imagery is
// the product layer rendered by our own /v1/tiles endpoints.
export const initMap = (container: HTMLElement) =>
  new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors",
        },
      },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#09090b" } },
        { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.55 } },
      ],
    },
    center: [22.9, 39.6],
    zoom: 7.5,
    attributionControl: { compact: true },
    // keeps the WebGL buffer readable — headless screenshots & future
    // "export view as image" both need it; minor perf cost
    canvasContextAttributes: { preserveDrawingBuffer: true },
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

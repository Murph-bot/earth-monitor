import { useCallback, useEffect, useRef, useState } from "react"
import type maplibregl from "maplibre-gl"
import { client, type Aoi, type MetricsResponse, type SceneSummary } from "./api"
import { EMPTY_FC, initMap, rectFeature, setGeoData } from "./map"
import { Sidebar } from "./components/Sidebar"

interface TileJson {
  tiles: string[]
  bounds: number[]
  minzoom?: number
  maxzoom?: number
}

const fc = (feature: GeoJSON.Feature): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: [feature],
})

export const App = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const drawRef = useRef<{ active: boolean; start: maplibregl.LngLat | null }>({
    active: false,
    start: null,
  })

  const [aois, setAois] = useState<Aoi[]>([])
  const [selectedAoi, setSelectedAoi] = useState<Aoi | null>(null)
  const [scenes, setScenes] = useState<SceneSummary[]>([])
  const [selectedScene, setSelectedScene] = useState<SceneSummary | null>(null)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [drawMode, setDrawMode] = useState(false)
  const [pendingGeom, setPendingGeom] = useState<GeoJSON.Polygon | null>(null)
  const [draftName, setDraftName] = useState("")
  const [notice, setNotice] = useState<string | null>(null)

  drawRef.current.active = drawMode

  const refreshAois = useCallback(async () => {
    const { data } = await client.GET("/v1/aois")
    setAois(data?.items ?? [])
  }, [])

  // --- map lifecycle -------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = initMap(containerRef.current)
    mapRef.current = map

    map.on("load", () => {
      map.addSource("aoi-geom", { type: "geojson", data: EMPTY_FC })
      map.addSource("draft", { type: "geojson", data: EMPTY_FC })
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aoi-geom",
        paint: { "fill-color": "#10b981", "fill-opacity": 0.12 },
      })
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi-geom",
        paint: { "line-color": "#10b981", "line-width": 1.5 },
      })
      map.addLayer({
        id: "draft-line",
        type: "line",
        source: "draft",
        paint: { "line-color": "#38bdf8", "line-width": 2, "line-dasharray": [2, 2] },
      })
    })

    map.on("mousedown", (e) => {
      if (!drawRef.current.active) return
      drawRef.current.start = e.lngLat
      map.dragPan.disable()
    })
    map.on("mousemove", (e) => {
      const { start } = drawRef.current
      if (!drawRef.current.active || !start) return
      setGeoData(map, "draft", fc(rectFeature(start, e.lngLat)))
    })
    map.on("mouseup", (e) => {
      const { start } = drawRef.current
      if (!drawRef.current.active || !start) return
      drawRef.current.start = null
      map.dragPan.enable()
      const geom = rectFeature(start, e.lngLat).geometry as GeoJSON.Polygon
      setPendingGeom(geom)
      setDrawMode(false)
    })

    return () => {
      mapRef.current = null
      map.remove()
    }
  }, [])

  useEffect(() => {
    void refreshAois()
  }, [refreshAois])

  // --- interactions ----------------------------------------------------------
  const handleSelectAoi = useCallback(async (a: Aoi) => {
    setSelectedAoi(a)
    setSelectedScene(null)
    const map = mapRef.current
    const [detailRes, scenesRes, metricsRes] = await Promise.all([
      client.GET("/v1/aois/{aoi_id}", { params: { path: { aoi_id: a.id } } }),
      client.GET("/v1/aois/{aoi_id}/scenes", { params: { path: { aoi_id: a.id } } }),
      client.GET("/v1/aois/{aoi_id}/metrics", { params: { path: { aoi_id: a.id } } }),
    ])
    setScenes(scenesRes.data?.items ?? [])
    setMetrics(metricsRes.data ?? null)
    if (map?.isStyleLoaded() && detailRes.data) {
      const geom = detailRes.data.geom as unknown as GeoJSON.Geometry
      setGeoData(map, "aoi-geom", fc({ type: "Feature", properties: {}, geometry: geom }))
      const b = detailRes.data.bbox
      map.fitBounds(
        [
          [b.minx, b.miny],
          [b.maxx, b.maxy],
        ],
        { padding: 60, duration: 600 },
      )
    }
  }, [])

  const handleSelectScene = useCallback(async (s: SceneSummary) => {
    setSelectedScene(s)
    const map = mapRef.current
    if (!map?.isStyleLoaded()) return
    const { data } = await client.GET("/v1/tiles/scenes/{scene_id}/tilejson.json", {
      params: { path: { scene_id: s.id } },
    })
    const tj = data as TileJson | undefined
    if (!tj) return
    // Tile URLs arrive absolute (server origin); in dev the vite proxy splits
    // origins, so pin them to the page origin — a no-op in prod same-origin.
    // (regex, not new URL() — it would percent-encode the {z}/{x}/{y} template)
    const tiles = tj.tiles.map((u) => u.replace(/^https?:\/\/[^/]+/, location.origin))
    if (map.getLayer("scene-tiles")) map.removeLayer("scene-tiles")
    if (map.getSource("scene")) map.removeSource("scene")
    map.addSource("scene", {
      type: "raster",
      tiles,
      minzoom: tj.minzoom,
      maxzoom: tj.maxzoom,
      attribution: "Contains modified Copernicus Sentinel data",
    })
    map.addLayer({ id: "scene-tiles", type: "raster", source: "scene" }, "aoi-fill")
  }, [])

  const handleCreateAoi = useCallback(async () => {
    if (!pendingGeom || !draftName.trim()) return
    const { error } = await client.POST("/v1/aois", {
      body: {
        name: draftName.trim(),
        geojson: pendingGeom as unknown as { [key: string]: unknown },
        is_public: false,
      },
    })
    if (error) {
      setNotice(`create failed: ${JSON.stringify(error).slice(0, 140)}`)
      return
    }
    setPendingGeom(null)
    setDraftName("")
    setGeoData(mapRef.current!, "draft", EMPTY_FC)
    await refreshAois()
  }, [pendingGeom, draftName, refreshAois])

  const handleDeleteAoi = useCallback(
    async (a: Aoi) => {
      await client.DELETE("/v1/aois/{aoi_id}", { params: { path: { aoi_id: a.id } } })
      setSelectedAoi(null)
      setScenes([])
      setMetrics(null)
      setGeoData(mapRef.current!, "aoi-geom", EMPTY_FC)
      await refreshAois()
    },
    [refreshAois],
  )

  const handleCancelDraft = useCallback(() => {
    setPendingGeom(null)
    setDraftName("")
    setGeoData(mapRef.current!, "draft", EMPTY_FC)
  }, [])

  // --- render ----------------------------------------------------------------
  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-11 items-center gap-3 border-b border-zinc-800 bg-zinc-950 px-4">
        <span className="font-mono text-sm font-semibold tracking-tight text-zinc-100">
          earth-monitor
        </span>
        <span className="font-mono text-[10px] text-zinc-600">/v1 · sentinel-2 · greece</span>
      </header>
      <div className="flex min-h-0 flex-1">
        <Sidebar
          aois={aois}
          selectedAoi={selectedAoi}
          scenes={scenes}
          selectedScene={selectedScene}
          metrics={metrics}
          drawing={drawMode}
          onSelectAoi={handleSelectAoi}
          onSelectScene={handleSelectScene}
          onStartDraw={() => setDrawMode(true)}
          onDeleteAoi={handleDeleteAoi}
        />
        <div className="relative flex-1">
          {/* wrapper owns positioning — maplibre overrides `position` on the
              map container itself, so it must not carry absolute/inset */}
          <div className="absolute inset-0">
            <div ref={containerRef} className="h-full w-full" />
          </div>
          {drawMode && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded bg-sky-500/90 px-3 py-1.5 font-mono text-xs text-zinc-950 shadow-lg">
              drag a rectangle to define the AOI
            </div>
          )}
          {pendingGeom && (
            <div className="absolute top-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/95 p-2 shadow-xl">
              <input
                autoFocus
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateAoi()}
                placeholder="AOI name"
                className="w-44 rounded bg-zinc-800 px-2 py-1 text-sm outline-none placeholder:text-zinc-600 focus:ring-1 focus:ring-emerald-500"
              />
              <button
                onClick={handleCreateAoi}
                disabled={!draftName.trim()}
                className="rounded bg-emerald-500 px-2.5 py-1 text-xs font-semibold text-zinc-950 disabled:opacity-40"
              >
                create
              </button>
              <button onClick={handleCancelDraft} className="text-xs text-zinc-500 hover:text-zinc-300">
                cancel
              </button>
            </div>
          )}
          {notice && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded bg-red-500/90 px-3 py-1.5 font-mono text-xs text-zinc-950">
              {notice}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from "react"
import type * as maplibregl from "maplibre-gl"
import {
  API_BASE,
  client,
  type Aoi,
  type AoiDetail,
  type MetricsResponse,
  type SceneSummary,
} from "./api"
import { AuthForm, clearToken, getToken } from "./auth"
import { EMPTY_FC, initMap, rectFeature, setGeoData } from "./map"
import { clearPending, loadPending, savePending, type PendingAoi } from "./pendingAoi"
import { navigate, useRoute } from "./router"
import { AlertsPage } from "./components/AlertsPage"
import { AreasPanel, type SceneLayer } from "./components/AreasPanel"
import type { SummaryState } from "./components/ChangeStrip"
import type { BackfillState } from "./components/EmptyAreaState"
import { ExplorePanel, drawnTitle } from "./components/ExplorePanel"
import { LandingPanel } from "./components/LandingPanel"
import { NotFound } from "./components/NotFound"
import { Sheet } from "./components/Sheet"
import { TopBar } from "./components/TopBar"
import { WakingServer } from "./components/WakingServer"

interface TileJson {
  tiles: string[]
  bounds: number[]
  minzoom?: number
  maxzoom?: number
}

type Server = "probing" | "up" | "waking"

const RETRY_MS = 5000
const WAKING_AFTER_MS = 3000 // AC 6: say "waking" within 3 s
const POLL_MS = 15_000
const POLL_MAX = 20 // ~5 min after a backfill starts
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const fc = (feature: GeoJSON.Feature): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: [feature],
})

export const App = () => {
  const route = useRoute()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const drawRef = useRef<{
    active: boolean
    start: maplibregl.LngLat | null
    last: maplibregl.LngLat | null
  }>({ active: false, start: null, last: null })

  const [signedIn, setSignedIn] = useState(() => !!getToken())
  const [server, setServer] = useState<Server>("probing")
  const [attempt, setAttempt] = useState(0)
  const [summary, setSummary] = useState<SummaryState>({ status: "loading" })

  const [aois, setAois] = useState<Aoi[]>([])
  const [aoisLoaded, setAoisLoaded] = useState(false)
  const [selectedAoi, setSelectedAoi] = useState<Aoi | null>(null)
  const [detail, setDetail] = useState<AoiDetail | null>(null)
  const [detailError, setDetailError] = useState(false)
  const [scenes, setScenes] = useState<SceneSummary[]>([])
  const [selectedScene, setSelectedScene] = useState<SceneSummary | null>(null)
  const [layer, setLayer] = useState<SceneLayer>("ndvi")
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [backfill, setBackfill] = useState<BackfillState>("idle")
  const [watching, setWatching] = useState(false)

  const [drawMode, setDrawMode] = useState(false)
  const [pendingGeom, setPendingGeom] = useState<GeoJSON.Polygon | null>(null)
  const [draftName, setDraftName] = useState("")
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const selectedAoiId = useRef<string | null>(null)

  drawRef.current.active = drawMode

  // --- server probe ----------------------------------------------------------
  // The API is on a free tier that sleeps (30-60 s cold start). Probe the
  // public /v1/health, say "waking" after 3 s, keep retrying every 5 s. The
  // map never waits on this.
  useEffect(() => {
    let cancelled = false
    const waking = setTimeout(() => setServer((s) => (s === "probing" ? "waking" : s)), WAKING_AFTER_MS)
    void (async () => {
      let n = 0
      while (!cancelled) {
        setAttempt(++n)
        const t0 = Date.now()
        try {
          const { response } = await client.GET("/v1/health", { signal: AbortSignal.timeout(RETRY_MS) })
          if (response.ok) {
            if (!cancelled) setServer("up")
            return
          }
        } catch {
          // cold start, DNS, CORS, timeout: keep trying
        }
        await sleep(Math.max(0, RETRY_MS - (Date.now() - t0)))
      }
    })()
    return () => {
      cancelled = true
      clearTimeout(waking)
    }
  }, [])

  // public numbers for the landing strip — no auth, no 401
  useEffect(() => {
    if (server !== "up") return
    let cancelled = false
    void client
      .GET("/v1/public/region/thessaly/summary")
      .then(({ data }) => {
        if (!cancelled) setSummary(data ? { status: "ready", data } : { status: "error" })
      })
      .catch(() => {
        if (!cancelled) setSummary({ status: "error" })
      })
    return () => {
      cancelled = true
    }
  }, [server])

  const refreshAois = useCallback(async () => {
    try {
      const { data, response } = await client.GET("/v1/aois")
      if (!data) return setNotice(`Couldn't load your areas (HTTP ${response.status}).`)
      setAois(data.items)
      setAoisLoaded(true)
    } catch {
      setNotice("Couldn't reach the server.")
    }
  }, [])

  // never call /v1/aois while logged out (AC 10, 20)
  useEffect(() => {
    if (signedIn && server === "up") void refreshAois()
  }, [signedIn, server, refreshAois])

  // --- route guards ----------------------------------------------------------
  useEffect(() => {
    if (!signedIn && (route.name === "areas" || route.name === "alerts")) navigate("/signin", { replace: true })
    if (signedIn && (route.name === "signin" || route.name === "signup")) navigate("/areas", { replace: true })
  }, [signedIn, route.name])

  // --- map lifecycle ---------------------------------------------------------
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
        paint: { "fill-color": "#34d399", "fill-opacity": 0.12 },
      })
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi-geom",
        paint: { "line-color": "#34d399", "line-width": 2 },
      })
      map.addLayer({
        id: "draft-fill",
        type: "fill",
        source: "draft",
        paint: { "fill-color": "#f4f4f5", "fill-opacity": 0.1 },
      })
      map.addLayer({
        id: "draft-line",
        type: "line",
        source: "draft",
        paint: { "line-color": "#f4f4f5", "line-width": 2, "line-dasharray": [2, 1.5] },
      })
    })

    // one rectangle gesture for mouse and touch
    const begin = (e: { lngLat: maplibregl.LngLat }) => {
      if (!drawRef.current.active) return
      drawRef.current.start = e.lngLat
      drawRef.current.last = e.lngLat
    }
    const move = (e: { lngLat: maplibregl.LngLat }) => {
      const { start } = drawRef.current
      if (!drawRef.current.active || !start) return
      drawRef.current.last = e.lngLat
      setGeoData(map, "draft", fc(rectFeature(start, e.lngLat)))
    }
    const end = (e: { lngLat?: maplibregl.LngLat }) => {
      const { start, last } = drawRef.current
      if (!drawRef.current.active || !start) return
      const to = e.lngLat ?? last ?? start
      drawRef.current.start = null
      drawRef.current.last = null
      const geom = rectFeature(start, to).geometry as GeoJSON.Polygon
      const [a, , c] = geom.coordinates[0] ?? []
      if (!a || !c || a[0] === c[0] || a[1] === c[1]) {
        setGeoData(map, "draft", EMPTY_FC) // a tap, not a drag
        return
      }
      setPendingGeom(geom)
      setDrawMode(false)
    }
    map.on("mousedown", begin)
    map.on("mousemove", move)
    map.on("mouseup", end)
    map.on("touchstart", begin)
    map.on("touchmove", move)
    map.on("touchend", end)

    return () => {
      mapRef.current = null
      map.remove()
    }
  }, [])

  // while drawing, drags draw instead of panning
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (drawMode) {
      map.dragPan.disable()
      map.getCanvas().style.cursor = "crosshair"
    } else {
      map.dragPan.enable()
      map.getCanvas().style.cursor = ""
    }
  }, [drawMode])

  // leaving /explore abandons a half-finished drawing, never a finished one
  useEffect(() => {
    if (route.name !== "explore") setDrawMode(false)
  }, [route.name])

  // --- area data -------------------------------------------------------------
  const loadDetail = useCallback(async (a: Aoi, opts: { fit: boolean }) => {
    try {
      const [detailRes, scenesRes, metricsRes] = await Promise.all([
        client.GET("/v1/aois/{aoi_id}", { params: { path: { aoi_id: a.id } } }),
        client.GET("/v1/aois/{aoi_id}/scenes", { params: { path: { aoi_id: a.id } } }),
        client.GET("/v1/aois/{aoi_id}/metrics", { params: { path: { aoi_id: a.id } } }),
      ])
      // a later click owns the panel; drop responses for an area no longer selected
      if (selectedAoiId.current !== a.id) return null
      setDetailError(!detailRes.data)
      setDetail(detailRes.data ?? null)
      setScenes(scenesRes.data?.items ?? [])
      setMetrics(metricsRes.data ?? null)
      const map = mapRef.current
      if (opts.fit && map?.isStyleLoaded() && detailRes.data) {
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
      return { scenes: scenesRes.data?.items.length ?? 0, series: metricsRes.data?.series.length ?? 0 }
    } catch {
      if (selectedAoiId.current === a.id) setDetailError(true)
      return null
    }
  }, [])

  const handleSelectAoi = useCallback(
    async (a: Aoi) => {
      if (selectedAoiId.current === a.id) {
        // second tap collapses the card
        selectedAoiId.current = null
        setSelectedAoi(null)
        setDetail(null)
        return
      }
      selectedAoiId.current = a.id
      setSelectedAoi(a)
      setSelectedScene(null)
      setDetail(null)
      setDetailError(false)
      setScenes([])
      setMetrics(null)
      setBackfill("idle")
      await loadDetail(a, { fit: true })
    },
    [loadDetail],
  )

  // after a backfill (or a new area) starts, re-read the area until scenes appear
  useEffect(() => {
    if (!watching || !selectedAoi) return
    let polls = 0
    const t = setInterval(async () => {
      const r = await loadDetail(selectedAoi, { fit: false })
      polls++
      if ((r && r.scenes > 0 && r.series > 0) || polls >= POLL_MAX) {
        setWatching(false)
        setBackfill("idle")
      }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [watching, selectedAoi, loadDetail])

  const showScene = useCallback(async (s: SceneSummary, which: SceneLayer) => {
    const map = mapRef.current
    if (!map?.isStyleLoaded()) return
    const { data } = await client.GET("/v1/tiles/scenes/{scene_id}/tilejson.json", {
      params: { path: { scene_id: s.id } },
    })
    const tj = data as TileJson | undefined
    if (!tj) return
    // Tile URLs arrive absolute (server origin). Rewrite them to the API
    // origin this build actually talks to — in dev that's the page origin
    // behind the vite proxy; in split-origin prod it's VITE_API_URL (usually
    // a no-op since tilejson already returns it). Regex, not new URL() —
    // URL parsing would percent-encode the {z}/{x}/{y} template.
    const tiles = tj.tiles.map(
      (u) => u.replace(/^https?:\/\/[^/]+/, API_BASE || location.origin) + (which === "ndvi" ? "?index=ndvi" : ""),
    )
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

  const handleSelectScene = useCallback(
    async (s: SceneSummary) => {
      setSelectedScene(s)
      await showScene(s, layer)
    },
    [showScene, layer],
  )

  const handleLayer = useCallback(
    (l: SceneLayer) => {
      setLayer(l)
      if (selectedScene) void showScene(selectedScene, l)
    },
    [selectedScene, showScene],
  )

  const handleBackfill = useCallback(async () => {
    if (!selectedAoi) return
    setBackfill("starting")
    try {
      const { response } = await client.POST("/v1/aois/{aoi_id}/backfill", {
        params: { path: { aoi_id: selectedAoi.id } },
      })
      // 202 = scheduled, 409 = already running: either way it is running
      if (response.status === 202 || response.status === 409) {
        setBackfill("running")
        setWatching(true)
      } else setBackfill("error")
    } catch {
      setBackfill("error")
    }
  }, [selectedAoi])

  // --- creating, saving, deleting ---------------------------------------------
  const createArea = useCallback(async (name: string, geometry: GeoJSON.Polygon) => {
    const { data, error } = await client.POST("/v1/aois", {
      body: { name, geojson: geometry as unknown as { [key: string]: unknown }, is_public: false },
    })
    if (error || !data) {
      const msg = (error as { error?: { message?: string } } | undefined)?.error?.message
      setNotice(`Couldn't save the area${msg ? `: ${msg}` : "."}`)
      return null
    }
    return data
  }, [])

  const clearDraft = useCallback(() => {
    setPendingGeom(null)
    setDraftName("")
    setDrawMode(false)
    if (mapRef.current?.isStyleLoaded()) setGeoData(mapRef.current, "draft", EMPTY_FC)
  }, [])

  // The API backfills new areas on its own; we just open the area and watch it.
  const openCreated = useCallback(
    async (area: Aoi, to: string) => {
      await refreshAois()
      selectedAoiId.current = area.id
      setSelectedAoi(area)
      setSelectedScene(null)
      setBackfill("running")
      setWatching(true)
      navigate(to)
      await loadDetail(area, { fit: true })
    },
    [refreshAois, loadDetail],
  )

  const handleSave = useCallback(
    async (intent: PendingAoi["intent"]) => {
      if (!pendingGeom) return
      if (!signedIn) {
        // draw-then-sign-up (AC 21): park the polygon, keep it through sign-up
        savePending({ geometry: pendingGeom, intent })
        navigate("/signup")
        return
      }
      setSaving(true)
      const area = await createArea(draftName.trim(), pendingGeom)
      setSaving(false)
      if (!area) return
      clearDraft()
      await openCreated(area, intent === "alert" ? `/areas/${area.id}/alerts` : "/areas")
    },
    [pendingGeom, signedIn, draftName, createArea, clearDraft, openCreated],
  )

  // after register/login: save the parked polygon to the new account, then clear it
  const handleAuthed = useCallback(async () => {
    setSignedIn(true)
    const pending = loadPending()
    if (!pending) return navigate("/areas")
    const area = await createArea("My first area", pending.geometry)
    clearPending() // saved, or unsaveable (too large etc.): either way it is spent
    clearDraft()
    if (!area) return navigate("/areas")
    await openCreated(area, pending.intent === "alert" ? `/areas/${area.id}/alerts` : "/areas")
  }, [createArea, clearDraft, openCreated])

  const handleDeleteAoi = useCallback(
    async (a: Aoi) => {
      await client.DELETE("/v1/aois/{aoi_id}", { params: { path: { aoi_id: a.id } } })
      selectedAoiId.current = null
      setSelectedAoi(null)
      setDetail(null)
      setScenes([])
      setMetrics(null)
      if (mapRef.current?.isStyleLoaded()) setGeoData(mapRef.current, "aoi-geom", EMPTY_FC)
      await refreshAois()
    },
    [refreshAois],
  )

  const handleSignOut = () => {
    clearToken()
    setSignedIn(false)
    setAois([])
    setAoisLoaded(false)
    selectedAoiId.current = null
    setSelectedAoi(null)
    setDetail(null)
    navigate("/")
  }

  // --- render ----------------------------------------------------------------
  const waking = server === "waking"
  const overlay =
    route.name === "signin" || route.name === "signup" || route.name === "alerts" || route.name === "notfound"

  const sheet = (() => {
    switch (route.name) {
      case "landing":
        return (
          <Sheet>
            <LandingPanel summary={summary} signedIn={signedIn} waking={waking} attempt={attempt} />
          </Sheet>
        )
      case "explore":
        return (
          <Sheet title={drawnTitle(pendingGeom)}>
            <ExplorePanel
              signedIn={signedIn}
              drawing={drawMode}
              pendingGeom={pendingGeom}
              draftName={draftName}
              busy={saving}
              onDraftName={setDraftName}
              onStartDraw={() => setDrawMode(true)}
              onCancel={clearDraft}
              onSave={handleSave}
            />
          </Sheet>
        )
      case "areas":
        return (
          <Sheet title="Saved areas">
            {waking ? (
              <WakingServer attempt={attempt} />
            ) : (
              <AreasPanel
                aois={aois}
                loaded={aoisLoaded}
                selectedAoi={selectedAoi}
                detail={detail}
                detailError={detailError}
                scenes={scenes}
                selectedScene={selectedScene}
                metrics={metrics}
                backfill={backfill}
                layer={layer}
                onLayer={handleLayer}
                onSelectAoi={handleSelectAoi}
                onSelectScene={handleSelectScene}
                onBackfill={handleBackfill}
                onDeleteAoi={handleDeleteAoi}
              />
            )}
          </Sheet>
        )
      default:
        return null
    }
  })()

  const Shell = overlay ? "div" : "main"
  return (
    <div className="flex h-svh flex-col">
      <TopBar signedIn={signedIn} onSignOut={handleSignOut} />
      <Shell className="relative min-h-0 flex-1">
        {/* wrapper owns positioning — maplibre overrides `position` on the
            map container itself, so it must not carry absolute/inset */}
        <div className="absolute inset-0">
          <div ref={containerRef} className="h-full w-full" />
        </div>
        {sheet}
        {drawMode && (
          <div
            role="status"
            className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-sm bg-accent px-3 py-1.5 text-sm font-semibold whitespace-nowrap text-accent-ink shadow-lg"
          >
            Drag a rectangle around your field
          </div>
        )}
        {overlay && (
          <div className="absolute inset-0 z-20 overflow-y-auto bg-bg">
            {waking && (route.name === "signin" || route.name === "signup") && (
              <div className="mx-auto max-w-[440px] p-4 pb-0">
                <WakingServer attempt={attempt} />
              </div>
            )}
            {route.name === "signin" && <AuthForm mode="signin" pending={loadPending()} onAuth={handleAuthed} />}
            {route.name === "signup" && <AuthForm mode="signup" pending={loadPending()} onAuth={handleAuthed} />}
            {route.name === "alerts" && signedIn && (
              <AlertsPage aoiId={route.aoiId} aois={aois} loaded={aoisLoaded} />
            )}
            {route.name === "notfound" && <NotFound />}
          </div>
        )}
        {notice && (
          <div
            role="alert"
            className="absolute bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-sm bg-danger-bg py-1 pr-1 pl-3 text-sm text-danger-ink"
          >
            {notice}
            <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss" className="rounded-sm px-2">
              ✕
            </button>
          </div>
        )}
      </Shell>
    </div>
  )
}

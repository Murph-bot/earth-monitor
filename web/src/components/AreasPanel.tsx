import type { Aoi, AoiDetail, MetricsResponse, SceneSummary } from "../api"
import { Link } from "../router"
import { AreaCard, type AreaStatus } from "./AreaCard"
import { DeleteArea } from "./DeleteArea"
import { EmptyAreaState, type BackfillState } from "./EmptyAreaState"
import { Legend } from "./Legend"
import { MetricChart } from "./MetricChart"
import { shortDate } from "../labels"

export type SceneLayer = "ndvi" | "truecolor"

const STALE_DAYS = 14

interface Props {
  aois: Aoi[]
  loaded: boolean
  selectedAoi: Aoi | null
  detail: AoiDetail | null
  detailError: boolean
  scenes: SceneSummary[]
  selectedScene: SceneSummary | null
  metrics: MetricsResponse | null
  backfill: BackfillState
  layer: SceneLayer
  onLayer: (l: SceneLayer) => void
  onSelectAoi: (a: Aoi) => void
  onSelectScene: (s: SceneSummary) => void
  onBackfill: () => void
  onDeleteAoi: (a: Aoi) => void
}

const statusOf = (p: Props): AreaStatus => {
  if (p.detailError) return "error"
  if (!p.detail) return "ok"
  if (p.scenes.length === 0) return "empty"
  const newest = p.scenes[0]?.acquired_at
  if (newest && Date.now() - new Date(newest).getTime() > STALE_DAYS * 86_400_000) return "stale"
  return "ok"
}

export const AreasPanel = (p: Props) => {
  const status = statusOf(p)
  const series = p.metrics?.series ?? []
  return (
    <>
      {p.loaded && p.aois.length === 0 && (
        <div className="mb-3">
          <p className="mb-3 text-muted">No areas yet.</p>
          <Link
            to="/explore"
            className="flex items-center justify-center rounded-sm bg-accent font-semibold text-accent-ink"
          >
            Draw an area on the map
          </Link>
        </div>
      )}
      {p.aois.length > 0 && (
        <Link
          to="/explore"
          className="mb-3 flex items-center justify-center rounded-sm bg-accent font-semibold text-accent-ink"
        >
          ＋ New area
        </Link>
      )}
      <ul className="space-y-2.5">
        {p.aois.map((a) => {
          const selected = p.selectedAoi?.id === a.id
          return (
            <AreaCard
              key={a.id}
              area={a}
              selected={selected}
              status={selected ? status : "ok"}
              onSelect={() => p.onSelectAoi(a)}
            >
              {status === "empty" && (
                <EmptyAreaState
                  nextPass={p.detail?.next_pass_estimate ?? null}
                  basis={p.detail?.next_pass_basis ?? null}
                  backfill={p.backfill}
                  onBackfill={p.onBackfill}
                />
              )}
              {series.length > 0 && (
                <div className="mt-3 space-y-4">
                  {series.map((s) => (
                    <MetricChart key={`${s.metric_name}:${s.sensor_id}`} series={s} />
                  ))}
                </div>
              )}
              {p.scenes.length > 0 && (
                <div className="mt-3">
                  <h3 className="mb-1.5 text-sm font-semibold">Satellite scenes</h3>
                  <ul className="max-h-56 space-y-1 overflow-y-auto">
                    {p.scenes.map((s) => (
                      <li key={s.id}>
                        <button
                          type="button"
                          onClick={() => p.onSelectScene(s)}
                          aria-pressed={p.selectedScene?.id === s.id}
                          className={`flex w-full items-center justify-between rounded-sm px-2 text-left text-sm ${
                            p.selectedScene?.id === s.id ? "bg-s4/20" : "hover:bg-surface-2"
                          }`}
                        >
                          <span>{shortDate(s.acquired_at)}</span>
                          <span className="font-mono text-xs text-muted">
                            cloud {s.cloud_cover === null ? "—" : `${s.cloud_cover.toFixed(0)}%`} · covers{" "}
                            {Math.round(s.coverage * 100)}%
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {p.selectedScene && (
                    <div className="mt-2">
                      <label htmlFor="scene-layer" className="mb-1.5 block text-sm font-semibold">
                        Map layer
                      </label>
                      <select
                        id="scene-layer"
                        value={p.layer}
                        onChange={(e) => p.onLayer(e.target.value as SceneLayer)}
                        className="w-full rounded-sm border border-border-ui bg-bg px-3 text-text"
                      >
                        <option value="ndvi">Greenness (NDVI)</option>
                        <option value="truecolor">True colour</option>
                      </select>
                      {p.layer === "ndvi" && <Legend className="mt-2" />}
                    </div>
                  )}
                </div>
              )}
              <div className="mt-3">
                <Link
                  to={`/areas/${a.id}/alerts`}
                  className="flex w-full items-center justify-center rounded-sm border border-border-ui font-semibold"
                >
                  Alerts for this area
                </Link>
              </div>
              <DeleteArea name={a.name} onDelete={() => p.onDeleteAoi(a)} />
            </AreaCard>
          )
        })}
      </ul>
    </>
  )
}

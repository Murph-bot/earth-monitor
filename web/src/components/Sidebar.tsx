import type { Aoi, MetricsResponse, SceneSummary } from "../api"
import { MetricChart } from "./MetricChart"
import { RulesPanel } from "./RulesPanel"

const km2 = (m2: number) => (m2 / 1e6).toFixed(1)
const pct = (x: number | null) => (x === null ? "—" : `${x.toFixed(0)}%`)

interface Props {
  aois: Aoi[]
  selectedAoi: Aoi | null
  scenes: SceneSummary[]
  selectedScene: SceneSummary | null
  metrics: MetricsResponse | null
  drawing: boolean
  onSelectAoi: (a: Aoi) => void
  onSelectScene: (s: SceneSummary) => void
  onStartDraw: () => void
  onDeleteAoi: (a: Aoi) => void
}

export const Sidebar = (p: Props) => (
  <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-r border-zinc-800 bg-zinc-900/60 p-4">
    <div className="flex items-center justify-between">
      <h2 className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">
        Areas of interest
      </h2>
      <button
        onClick={p.onStartDraw}
        className={`rounded px-2 py-1 text-xs font-medium ${
          p.drawing
            ? "bg-emerald-500 text-zinc-950"
            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
        }`}
      >
        {p.drawing ? "drag on map…" : "+ new AOI"}
      </button>
    </div>

    {p.aois.length === 0 && (
      <p className="text-xs text-zinc-500">No AOIs yet — draw one on the map.</p>
    )}

    <ul className="space-y-1">
      {p.aois.map((a) => (
        <li key={a.id}>
          <button
            onClick={() => p.onSelectAoi(a)}
            className={`w-full rounded px-2 py-1.5 text-left text-sm transition-colors ${
              p.selectedAoi?.id === a.id
                ? "bg-emerald-500/15 text-emerald-300"
                : "text-zinc-300 hover:bg-zinc-800"
            }`}
          >
            <span className="block truncate">{a.name}</span>
            <span className="font-mono text-[10px] text-zinc-500">{km2(a.area_m2)} km²</span>
          </button>
        </li>
      ))}
    </ul>

    {p.selectedAoi && (
      <>
        <div className="flex items-center justify-between border-t border-zinc-800 pt-3">
          <h2 className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">
            Scenes
          </h2>
          <button
            onClick={() => p.onDeleteAoi(p.selectedAoi!)}
            className="text-[10px] text-red-400/70 hover:text-red-400"
          >
            delete AOI
          </button>
        </div>
        <ul className="max-h-56 space-y-1 overflow-y-auto">
          {p.scenes.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => p.onSelectScene(s)}
                className={`w-full rounded px-2 py-1.5 text-left font-mono text-xs ${
                  p.selectedScene?.id === s.id
                    ? "bg-sky-500/15 text-sky-300"
                    : "text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                <span className="block">{s.acquired_at.slice(0, 10)}</span>
                <span className="text-[10px] text-zinc-600">
                  cloud {pct(s.cloud_cover)} · cover {Math.round(s.coverage * 100)}%
                </span>
              </button>
            </li>
          ))}
          {p.scenes.length === 0 && (
            <li className="text-xs text-zinc-500">No scenes ingested for this AOI yet.</li>
          )}
        </ul>
      </>
    )}

    {p.metrics && p.metrics.series.length > 0 && (
      <div className="space-y-4 border-t border-zinc-800 pt-3">
        {p.metrics.series.map((s) => (
          <MetricChart key={`${s.metric_name}:${s.sensor_id}`} series={s} />
        ))}
      </div>
    )}

    {p.selectedAoi && <RulesPanel aoiId={p.selectedAoi.id} series={p.metrics?.series ?? []} />}
  </aside>
)

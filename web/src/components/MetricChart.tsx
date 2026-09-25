import type { MetricSeries } from "../api"

// Hand-rolled sparkline — the payload is small (points per scene), so an
// SVG polyline beats pulling in a chart library.
const W = 264
const H = 88
const PAD = 8

const SCALE = (v: number, min: number, max: number, outMin: number, outMax: number) =>
  max === min ? (outMin + outMax) / 2 : outMin + ((v - min) / (max - min)) * (outMax - outMin)

export const MetricChart = ({ series }: { series: MetricSeries }) => {
  const pts = [...series.points].sort((a, b) => a.date.localeCompare(b.date))
  const values = pts.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const lo = min - span * 0.1
  const hi = max + span * 0.1

  const coords = pts.map((p, i) => ({
    x: SCALE(i, 0, Math.max(pts.length - 1, 1), PAD, W - PAD),
    y: SCALE(p.value, lo, hi, H - PAD, PAD),
    ...p,
  }))
  const line = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ")

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-xs text-zinc-400">{series.metric_name}</span>
        <span className="font-mono text-[10px] text-zinc-600">{series.unit}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full">
        <polyline
          points={line}
          fill="none"
          strokeWidth="1.5"
          className="stroke-emerald-400"
        />
        {coords.map((c) => (
          <circle key={c.scene_id} cx={c.x} cy={c.y} r="2.5" className="fill-emerald-300">
            <title>
              {c.date} — {c.value.toFixed(3)} ({Math.round(c.valid_pixel_pct * 100)}% valid)
            </title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between font-mono text-[10px] text-zinc-600">
        <span>{pts[0]?.date}</span>
        <span>{pts[pts.length - 1]?.date}</span>
      </div>
    </div>
  )
}

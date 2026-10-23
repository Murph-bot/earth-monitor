import type { MetricSeries } from "../api"
import { metricLabel } from "../labels"

// Hand-rolled sparkline — the payload is small (points per scene), so an
// SVG polyline beats pulling in a chart library.
const W = 264
const H = 88
const PAD = 8

const SCALE = (v: number, min: number, max: number, outMin: number, outMax: number) =>
  max === min ? (outMin + outMax) / 2 : outMin + ((v - min) / (max - min)) * (outMax - outMin)

// Thessaly scale s0..s5 over NDVI 0..0.8 — the same ramp as the map tiles
// (backend/app/tiles/render.py). Values stay in the tooltip: never colour alone.
const NDVI_MAX = 0.8
const scaleVar = (v: number) =>
  `var(--color-s${Math.min(5, Math.max(0, Math.round((v / NDVI_MAX) * 5)))})`

export const MetricChart = ({ series }: { series: MetricSeries }) => {
  const isNdvi = series.metric_name === "ndvi_mean"
  const isRain = series.metric_name === "rain_mm"
  const lineColor = isRain ? "var(--color-rain)" : "var(--color-s4)"
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
  const last = pts[pts.length - 1]

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold">{metricLabel(series.metric_name)}</span>
        {last && (
          <span className="font-mono text-sm text-muted">
            {last.value.toFixed(isNdvi ? 2 : 1)} {series.unit === "index" ? "" : series.unit}
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full" role="img" aria-label={`${metricLabel(series.metric_name)} over time`}>
        <polyline points={line} fill="none" strokeWidth="2" stroke={lineColor} />
        {coords.map((c) => (
          <circle
            key={`${c.date}:${c.scene_id}`}
            cx={c.x}
            cy={c.y}
            r="3"
            fill={isNdvi ? scaleVar(c.value) : lineColor}
          >
            <title>
              {c.date} — {c.value.toFixed(3)}
              {/* daily sources (rain, UV) have no scene and no pixel mask */}
              {c.scene_id !== null && ` (${Math.round(c.valid_pixel_pct * 100)}% valid)`}
            </title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between font-mono text-xs text-muted">
        <span>{pts[0]?.date}</span>
        <span>{last?.date}</span>
      </div>
    </div>
  )
}

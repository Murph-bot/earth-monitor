import { dataDateLabel, type OverviewKind, type OverviewLayer } from "../overview"

interface Props {
  on: boolean
  kind: OverviewKind
  layer: OverviewLayer | null
  regionZoomed: boolean
  onToggle: () => void
  onKind: (k: OverviewKind) => void
  onAllGreece: () => void
}

const btn =
  "flex items-center justify-center rounded-sm border border-border bg-bg/90 px-3 text-sm font-semibold"

// Corner control (desktop) / full-width block above the sheet (phone):
// overview on/off, Greenness|Rain, legend + data date + NASA GIBS credit.
export const OverviewControl = (p: Props) => (
  <div
    data-testid="map-controls"
    className="absolute inset-x-3 bottom-[calc(32svh+8px)] z-[5] flex flex-col gap-1.5 desk:inset-x-auto desk:right-3 desk:bottom-9 desk:w-[300px] desk:items-stretch"
  >
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      {p.regionZoomed && (
        <button type="button" onClick={p.onAllGreece} className={btn}>
          All Greece
        </button>
      )}
      <button
        type="button"
        aria-pressed={p.on}
        onClick={p.onToggle}
        className={btn}
        title="Greece overview background layer"
      >
        Overview: {p.on ? "on" : "off"}
      </button>
      <div role="group" aria-label="Overview layer" className="flex gap-1">
        {(["greenness", "rain"] as const).map((k) => (
          <button
            key={k}
            type="button"
            aria-pressed={p.kind === k}
            disabled={!p.on}
            onClick={() => p.onKind(k)}
            className={`${btn} disabled:opacity-50 ${p.kind === k ? "border-accent text-accent" : ""}`}
          >
            {k === "greenness" ? "Greenness" : "Rain"}
          </button>
        ))}
      </div>
    </div>
    {p.on && (
      <div className="rounded-sm border border-border bg-bg/90 px-3 py-2 text-xs leading-snug">
        <b className="font-semibold">Coarse overview, ~500 m greenness and ~10 km rain</b>
        <div className="text-muted" data-testid="overview-date">
          {p.layer ? dataDateLabel(p.layer) : "Loading overview…"}
        </div>
        <div className="text-muted">Detailed figures come from the fields you draw.</div>
        <div className="text-muted">Imagery: NASA GIBS</div>
      </div>
    )}
  </div>
)

import type { RegionSummary } from "../api"

export type SummaryState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: RegionSummary }

const Chip = ({ label, children, note }: { label: string; children: React.ReactNode; note: string }) => (
  <div className="min-w-[170px] flex-none rounded-[12px] border border-surface-2 bg-surface px-3.5 py-2.5">
    <span className="text-muted">{label}</span>
    <b className="block text-xl whitespace-nowrap">{children}</b>
    <span className="text-[13px] text-muted">{note}</span>
  </div>
)

const Skeleton = () => (
  <div className="flex gap-2.5" aria-busy="true" aria-label="Loading this week's numbers">
    {[0, 1, 2].map((i) => (
      <div key={i} className="h-[88px] min-w-[170px] animate-pulse rounded-[12px] bg-surface-2" />
    ))}
  </div>
)

// "What changed this week": three chips from the public summary. Every
// number is the API's; a null renders as "no data", never a placeholder.
export const ChangeStrip = ({ state }: { state: SummaryState }) => {
  if (state.status === "loading") return <Skeleton />
  if (state.status === "error")
    return <p className="text-sm text-muted">This week's numbers couldn't be loaded right now.</p>

  const { greenness, rain, scenes, window_days, name } = state.data
  const delta = greenness.delta
  const trend =
    delta === null ? "" : Math.abs(delta) < 0.005 ? "≈ " : delta < 0 ? "▼ " : "▲ "
  const trendClass =
    delta === null || Math.abs(delta) < 0.005 ? "" : delta < 0 ? "text-warn" : "text-accent"
  const noScenes = scenes.clear + scenes.cloudy === 0

  return (
    <div className="flex gap-2.5 overflow-x-auto pb-1">
      <Chip
        label={`${name} greenness`}
        note={
          delta === null
            ? greenness.mean === null
              ? "no clear scenes yet"
              : "no week-earlier value to compare"
            : delta < -0.005
              ? "less green than last week"
              : delta > 0.005
                ? "greener than last week"
                : "about the same as last week"
        }
      >
        {greenness.mean === null ? (
          "—"
        ) : (
          <span className={trendClass}>
            {greenness.mean.toFixed(2)}
            {delta !== null && ` ${trend}${Math.abs(delta).toFixed(2)}`}
          </span>
        )}
      </Chip>
      <Chip
        label={`Rain, last ${window_days} days`}
        note={rain.mean_mm === null ? "no rain data yet" : "average over monitored areas"}
      >
        {rain.mean_mm === null ? "—" : <span className="text-rain">{rain.mean_mm.toFixed(0)} mm</span>}
      </Chip>
      <Chip
        label="Clear scenes"
        note={
          noScenes
            ? "no new scenes this week"
            : `${scenes.cloudy} cloudy skipped`
        }
      >
        {scenes.clear}
      </Chip>
    </div>
  )
}

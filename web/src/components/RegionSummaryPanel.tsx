import { ChangeStrip, type SummaryState } from "./ChangeStrip"

const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return "—"
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
}

// Region summary shown when a public region is tapped on the Greece map.
// Reuses the landing ChangeStrip chips, plus scene counts and dates.
export const RegionSummaryPanel = ({
  state,
  onClose,
}: {
  state: SummaryState
  onClose: () => void
}) => (
  <div data-testid="region-summary" className="flex flex-col gap-2.5">
    <ChangeStrip state={state} />
    {state.status === "ready" && (
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted">Scenes (clear / cloudy)</dt>
        <dd>
          {state.data.scenes.clear} / {state.data.scenes.cloudy}
        </dd>
        <dt className="text-muted">Latest scene</dt>
        <dd>{fmtDate(state.data.scenes.latest_scene_at)}</dd>
        <dt className="text-muted">Window</dt>
        <dd>Last {state.data.window_days} days</dd>
        <dt className="text-muted">Updated</dt>
        <dd>{fmtDate(state.data.generated_at)}</dd>
      </dl>
    )}
    <button
      type="button"
      onClick={onClose}
      className="self-start rounded-sm border border-border px-3 py-1.5 text-sm font-semibold"
    >
      Back to all Greece
    </button>
  </div>
)

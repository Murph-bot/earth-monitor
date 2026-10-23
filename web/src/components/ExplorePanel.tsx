import { polygonKm2 } from "../pendingAoi"

interface Props {
  signedIn: boolean
  drawing: boolean
  pendingGeom: GeoJSON.Polygon | null
  draftName: string
  busy: boolean
  onDraftName: (v: string) => void
  onStartDraw: () => void
  onCancel: () => void
  onSave: (intent: "save" | "alert") => void
}

// Draw an area → keep it → save / alert. Looking never needs an account;
// saving does, and the drawn polygon survives the sign-up (pendingAoi.ts).
export const ExplorePanel = (p: Props) => {
  if (p.pendingGeom) {
    return (
      <div>
        <p className="mb-3 text-muted">
          Saving gives you weekly greenness and daily rain for this area.
        </p>
        {p.signedIn && (
          <div className="mb-3">
            <label htmlFor="area-name" className="mb-1.5 block text-sm font-semibold">
              Area name
            </label>
            <input
              id="area-name"
              value={p.draftName}
              onChange={(e) => p.onDraftName(e.target.value)}
              placeholder="e.g. North field"
              className="w-full rounded-sm border border-border-ui bg-bg px-3 text-text"
            />
          </div>
        )}
        <div className="flex flex-wrap gap-2.5">
          <button
            type="button"
            disabled={p.busy || (p.signedIn && !p.draftName.trim())}
            onClick={() => p.onSave("save")}
            className="rounded-sm bg-accent px-[18px] font-semibold text-accent-ink disabled:opacity-60"
          >
            {p.signedIn ? "Save this area" : "Save this area — free account"}
          </button>
          <button
            type="button"
            disabled={p.busy || (p.signedIn && !p.draftName.trim())}
            onClick={() => p.onSave("alert")}
            className="rounded-sm border border-border bg-surface-2 px-[18px] font-semibold disabled:opacity-60"
          >
            Set an alert
          </button>
          <button
            type="button"
            onClick={p.onCancel}
            className="rounded-sm border border-border px-[18px] font-semibold"
          >
            Discard
          </button>
        </div>
        {!p.signedIn && (
          <p className="mt-2 text-[13px] text-muted">
            Saving and alerts need an account. Looking never does.
          </p>
        )}
      </div>
    )
  }
  return (
    <div>
      <p className="mb-3 text-muted">
        {p.drawing
          ? "Drag a rectangle on the map around your field."
          : "Draw any field or area in Thessaly. No account needed to look."}
      </p>
      <button
        type="button"
        onClick={p.drawing ? p.onCancel : p.onStartDraw}
        className={`rounded-sm px-[18px] font-semibold ${
          p.drawing ? "border border-border bg-surface-2" : "bg-accent text-accent-ink"
        }`}
      >
        {p.drawing ? "Cancel drawing" : "✏️ Draw an area"}
      </button>
    </div>
  )
}

export const drawnTitle = (g: GeoJSON.Polygon | null) =>
  g ? `Your drawn area · ${polygonKm2(g).toFixed(1)} km²` : "Explore Thessaly"

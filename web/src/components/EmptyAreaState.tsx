import { shortDate } from "../labels"

export type BackfillState = "idle" | "starting" | "running" | "error"

// A new area has no scenes until the next Sentinel-2 pass (or a backfill):
// say so, give the estimated date, and offer to fill in the past 90 days.
export const EmptyAreaState = ({
  nextPass,
  basis,
  backfill,
  onBackfill,
}: {
  nextPass: string | null
  basis: "last_scene_cadence" | "revisit_upper_bound" | null
  backfill: BackfillState
  onBackfill: () => void
}) => (
  <div className="mt-2.5 rounded-md border border-[#a16207] bg-surface p-4">
    <p className="mb-1 font-bold">⏳ Collecting first data</p>
    <p className="mb-2.5 text-sm text-muted">
      No satellite scenes yet.{" "}
      {nextPass ? (
        <>
          The next Sentinel‑2 pass over this area is expected{" "}
          <b className="text-text">
            {basis === "revisit_upper_bound" ? "by " : "≈ "}
            {shortDate(nextPass)}
          </b>
          ; numbers usually appear within 24 h of a clear pass.
        </>
      ) : (
        "Numbers appear within 24 h of the next clear pass."
      )}{" "}
      Rainfall is filled in from the past 90 days when the backfill finishes.
    </p>
    {backfill === "running" ? (
      <p role="status" className="text-sm text-accent">
        Backfill running — scenes appear here as they're found (a few minutes).
      </p>
    ) : (
      <>
        <button
          type="button"
          onClick={onBackfill}
          disabled={backfill === "starting"}
          className="rounded-sm bg-accent px-[18px] font-semibold text-accent-ink disabled:opacity-60"
        >
          {backfill === "starting" ? "Starting…" : "Backfill last 90 days"}
        </button>
        {backfill === "error" && (
          <p role="alert" className="mt-2 text-sm text-danger">
            Couldn't start the backfill. Try again in a minute.
          </p>
        )}
      </>
    )}
  </div>
)

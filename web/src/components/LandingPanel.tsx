import type { RegionOut } from "../api"
import { BRAND, BRAND_SUBTITLE, REGIONS_LABEL } from "../brand"
import { Link } from "../router"
import { ChangeStrip, type SummaryState } from "./ChangeStrip"
import { WakingServer } from "./WakingServer"

// The public first screen: what the product does, in one line, before any form.
export const LandingPanel = ({
  summary,
  signedIn,
  waking,
  attempt,
  regions,
  region,
  onRegion,
}: {
  summary: SummaryState
  signedIn: boolean
  waking: boolean
  attempt: number
  regions: RegionOut[]
  region: string
  onRegion: (slug: string) => void
}) => (
  <div>
    <p className="mb-1.5 font-mono text-[13px] text-muted">
      <span lang="el">{BRAND_SUBTITLE}</span> · {REGIONS_LABEL} · Sentinel‑2 / Landsat
    </p>
    <h1 className="mb-2.5 text-2xl leading-tight font-bold desk:text-[28px]">
      {BRAND} shows how green and how wet your land is — every week, free.
    </h1>
    <p className="mb-3.5 text-muted">
      Draw any field or area. Get satellite greenness and daily rainfall as plain numbers. No
      account needed to look.
    </p>
    <div className="mb-3.5 flex flex-wrap gap-2.5">
      <Link
        to="/explore"
        className="flex items-center rounded-sm bg-accent px-[18px] font-semibold text-accent-ink"
      >
        Explore the map
      </Link>
      <Link
        to={signedIn ? "/areas" : "/signup"}
        className="flex items-center rounded-sm border border-border bg-surface-2 px-[18px] font-semibold"
      >
        {signedIn ? "Your areas" : "Create free account"}
      </Link>
    </div>
    <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-[15px] font-bold">What changed this week</h2>
      {regions.length > 1 && (
        <div role="group" aria-label="Region" className="flex gap-1">
          {regions.map((r) => (
            <button
              key={r.slug}
              type="button"
              aria-pressed={region === r.slug}
              onClick={() => onRegion(r.slug)}
              className={`rounded-sm border px-3 text-sm font-semibold ${
                region === r.slug ? "border-accent text-accent" : "border-border"
              }`}
            >
              {r.name}
            </button>
          ))}
        </div>
      )}
    </div>
    {waking ? <WakingServer attempt={attempt} /> : <ChangeStrip state={summary} />}
  </div>
)

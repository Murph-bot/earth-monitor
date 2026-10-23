import type { ReactNode } from "react"
import type { Aoi } from "../api"
import { km2 } from "../labels"

export type AreaStatus = "ok" | "empty" | "stale" | "error"

const BADGE: Record<Exclude<AreaStatus, "ok">, { text: string; cls: string }> = {
  empty: { text: "Collecting first data", cls: "text-warn" },
  stale: { text: "No clear scene for 14+ days", cls: "text-warn" },
  error: { text: "Couldn't load", cls: "text-danger" },
}

// One saved area. Selecting it expands `children` (details) beneath the header.
export const AreaCard = ({
  area,
  selected,
  status,
  onSelect,
  children,
}: {
  area: Aoi
  selected: boolean
  status: AreaStatus
  onSelect: () => void
  children?: ReactNode
}) => (
  <li
    className={`rounded-md border bg-bg p-3 ${
      status === "empty" ? "border-[#a16207]" : selected ? "border-s4" : "border-surface-2"
    }`}
  >
    <button
      type="button"
      onClick={onSelect}
      aria-expanded={selected}
      className="flex w-full flex-col items-start text-left"
    >
      <span className="flex w-full items-center justify-between gap-2">
        <b className="truncate">{area.name}</b>
        <span className="font-mono text-sm whitespace-nowrap text-muted">{km2(area.area_m2)} km²</span>
      </span>
      {status !== "ok" && (
        <span className={`text-sm ${BADGE[status].cls}`}>{BADGE[status].text}</span>
      )}
    </button>
    {selected && children}
  </li>
)

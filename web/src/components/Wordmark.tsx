import { BRAND, BRAND_SUBTITLE } from "../brand"

// Wordmark + the scale underline; the Greek subtitle sits beside it and is
// hidden below 420px so the title never wraps.
export const Wordmark = ({ greek = true }: { greek?: boolean }) => (
  <span className="inline-flex items-baseline gap-2.5 whitespace-nowrap">
    <span className="relative inline-block pb-1 text-[22px] font-extrabold tracking-tight">
      {BRAND}
      <i aria-hidden="true" className="scale-bar absolute inset-x-0 bottom-0 h-1 rounded-sm" />
    </span>
    {greek && (
      <span lang="el" className="text-sm font-medium text-muted max-[420px]:hidden">
        {BRAND_SUBTITLE}
      </span>
    )}
  </span>
)

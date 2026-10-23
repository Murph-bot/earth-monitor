// "Kampos" + the Thessaly-scale underline; Κάμπος ("the plain") sits beside
// it and is hidden below 360px so the title never wraps.
export const Wordmark = ({ greek = true }: { greek?: boolean }) => (
  <span className="inline-flex items-baseline gap-2.5 whitespace-nowrap">
    <span className="relative inline-block pb-1 text-[22px] font-extrabold tracking-tight">
      Kampos
      <i aria-hidden="true" className="scale-bar absolute inset-x-0 bottom-0 h-1 rounded-sm" />
    </span>
    {greek && (
      <span lang="el" className="text-sm font-medium text-muted max-[360px]:hidden">
        Κάμπος
      </span>
    )}
  </span>
)

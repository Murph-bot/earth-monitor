// Scale key for the greenness layer. Numbers are shown, never colour alone.
export const Legend = ({ className = "" }: { className?: string }) => (
  <div className={`rounded-sm border border-border bg-bg/90 px-3 py-2.5 text-[13px] ${className}`}>
    <b>Greenness (NDVI)</b>
    <div className="scale-bar my-1.5 h-2.5 rounded-sm" />
    <div className="flex justify-between text-xs text-muted">
      <span>Bare / dry 0.0</span>
      <span>Lush 0.8</span>
    </div>
  </div>
)

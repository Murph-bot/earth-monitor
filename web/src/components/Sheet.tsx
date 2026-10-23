import { useState, type ReactNode } from "react"

// Phone (<900px): bottom sheet that peeks at <=32svh so the map keeps >=60%
// of the screen; the handle expands it. Desktop (>=900px): floating 380px
// panel. The title is a single truncated line.
export const Sheet = ({ title, children }: { title?: string; children: ReactNode }) => {
  const [open, setOpen] = useState(false)
  return (
    <section
      aria-label={title ?? "Details"}
      className={`absolute inset-x-0 bottom-0 z-10 overflow-y-auto rounded-t-lg border-t border-border bg-surface px-4 pb-4 desk:inset-x-auto desk:top-4 desk:bottom-auto desk:left-4 desk:max-h-[calc(100%-2rem)] desk:w-[380px] desk:rounded-md desk:border ${
        open ? "max-h-[85svh]" : "max-h-[32svh]"
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={open ? "Collapse panel" : "Expand panel"}
        className="mx-auto flex w-full items-center justify-center desk:hidden"
      >
        <span className="h-[5px] w-10 rounded-sm bg-border-ui" />
      </button>
      {title && (
        <h2 className="mb-2.5 truncate text-lg font-bold whitespace-nowrap desk:mt-4">{title}</h2>
      )}
      {children}
    </section>
  )
}

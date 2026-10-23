import { useState } from "react"

// Lives under the collapsed "Area settings", 24px+ away from other buttons;
// deleting needs a confirm card that names the area and what is lost.
export const DeleteArea = ({ name, onDelete }: { name: string; onDelete: () => void }) => {
  const [confirming, setConfirming] = useState(false)
  return (
    <details className="mt-4">
      <summary className="flex w-full cursor-pointer items-center rounded-sm border border-border px-3 font-semibold">
        Area settings
      </summary>
      <div className="mt-3 border-t border-surface-2 pt-6">
        {!confirming ? (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-sm border border-[#7f1d1d] px-[18px] font-semibold text-danger"
          >
            Delete area…
          </button>
        ) : (
          <div role="alertdialog" aria-label={`Delete ${name}`} className="rounded-md border border-[#7f1d1d] bg-surface p-4">
            <b>Delete “{name}”?</b>
            <p className="my-2 text-sm text-muted">
              Its history and alerts will be removed. This can't be undone.
            </p>
            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded-sm border border-border bg-surface-2 px-[18px] font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onDelete}
                className="rounded-sm bg-danger-bg px-[18px] font-semibold text-danger-ink"
              >
                Delete
              </button>
            </div>
          </div>
        )}
      </div>
    </details>
  )
}

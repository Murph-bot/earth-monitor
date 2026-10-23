// Shown within 3 s when the API probe hasn't answered (Render free tier cold
// start, 30-60 s). The map stays usable underneath.
export const WakingServer = ({ attempt }: { attempt: number }) => (
  <div role="status">
    <h2 className="mb-2.5 text-lg font-bold">Waking up the server…</h2>
    <p className="mb-3 text-muted">
      Our free server sleeps when idle. This takes up to a minute — the map is already here, so look
      around meanwhile.
    </p>
    <div className="h-2 overflow-hidden rounded-sm bg-surface-2">
      <div className="h-full w-1/2 animate-pulse rounded-sm bg-accent" />
    </div>
    <p className="mt-2 font-mono text-[13px] text-muted">Retrying every 5 s · attempt {attempt}</p>
  </div>
)

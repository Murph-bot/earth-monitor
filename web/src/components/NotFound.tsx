import { Link } from "../router"

export const NotFound = () => (
  <main className="mx-auto my-[12vh] max-w-[760px] p-4 text-center">
    <h1 className="mb-2.5 text-[clamp(26px,4vw,40px)] leading-tight font-bold">
      This place isn't on the map.
    </h1>
    <p className="mb-4 text-muted">The page you followed doesn't exist or moved.</p>
    <Link
      to="/"
      className="inline-flex items-center justify-center rounded-sm bg-accent px-[18px] font-semibold text-accent-ink"
    >
      Back to the map
    </Link>
  </main>
)

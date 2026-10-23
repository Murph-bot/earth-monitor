import { Link } from "../router"
import { NotificationsBell } from "./NotificationsBell"
import { Wordmark } from "./Wordmark"

const action = "flex items-center rounded-sm border border-border px-3 text-sm font-semibold"

export const TopBar = ({ signedIn, onSignOut }: { signedIn: boolean; onSignOut: () => void }) => (
  <header className="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-surface-2 bg-bg px-4">
    <Link to="/" className="flex items-center" aria-label="Kampos — home">
      <Wordmark />
    </Link>
    <div className="flex items-center gap-1.5">
      {signedIn ? (
        <>
          <NotificationsBell />
          <Link to="/areas" className={action}>
            Areas
          </Link>
          <button type="button" onClick={onSignOut} className={action}>
            Sign out
          </button>
        </>
      ) : (
        <Link to="/signin" className={action}>
          Sign in
        </Link>
      )}
    </div>
  </header>
)

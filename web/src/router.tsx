import { useSyncExternalStore, type MouseEvent, type ReactNode } from "react"

// Five client routes, no router dependency. Keep in step with
// web/public/_redirects: every path matched here must have a rewrite there.
export type Route =
  | { name: "landing" }
  | { name: "explore" }
  | { name: "areas" }
  | { name: "alerts"; aoiId: string }
  | { name: "signin" }
  | { name: "signup" }
  | { name: "notfound" }

export const parseRoute = (pathname: string): Route => {
  const path = pathname.replace(/\/+$/, "") || "/"
  if (path === "/") return { name: "landing" }
  if (path === "/explore") return { name: "explore" }
  if (path === "/areas") return { name: "areas" }
  if (path === "/signin") return { name: "signin" }
  if (path === "/signup") return { name: "signup" }
  const alerts = /^\/areas\/([^/]+)\/alerts$/.exec(path)
  if (alerts?.[1]) return { name: "alerts", aoiId: decodeURIComponent(alerts[1]) }
  return { name: "notfound" }
}

const subscribe = (cb: () => void) => {
  window.addEventListener("popstate", cb)
  return () => window.removeEventListener("popstate", cb)
}

export const useRoute = (): Route => {
  const path = useSyncExternalStore(subscribe, () => location.pathname)
  return parseRoute(path)
}

export const navigate = (to: string, opts: { replace?: boolean } = {}) => {
  if (location.pathname === to) return
  if (opts.replace) history.replaceState(null, "", to)
  else history.pushState(null, "", to)
  window.dispatchEvent(new PopStateEvent("popstate"))
}

export const Link = ({
  to,
  className,
  children,
  ...rest
}: {
  to: string
  className?: string
  children: ReactNode
  "aria-label"?: string
}) => (
  <a
    href={to}
    className={className}
    {...rest}
    onClick={(e: MouseEvent<HTMLAnchorElement>) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
      e.preventDefault()
      navigate(to)
    }}
  >
    {children}
  </a>
)

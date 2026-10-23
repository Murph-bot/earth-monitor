import { useEffect, useRef } from "react"

// Cloudflare Turnstile widget. Renders nothing unless VITE_TURNSTILE_SITE_KEY
// is set at build time (a site key is public, but we never invent one).
// The token is only a claim — the API verifies it server-side when
// EM_TURNSTILE_SECRET is set.
export const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || undefined

interface TurnstileApi {
  render: (
    el: HTMLElement,
    opts: {
      sitekey: string
      theme: "dark"
      callback: (token: string) => void
      "expired-callback": () => void
      "error-callback": () => void
    },
  ) => string
  remove: (id: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

const SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
let loading: Promise<void> | null = null

const loadScript = () => {
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script")
    s.src = SRC
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => {
      loading = null
      reject(new Error("turnstile failed to load"))
    }
    document.head.appendChild(s)
  })
  return loading
}

export const Turnstile = ({ onToken }: { onToken: (token: string | null) => void }) => {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !ref.current) return
    let widgetId: string | undefined
    let cancelled = false
    loadScript()
      .then(() => {
        if (cancelled || !ref.current || !window.turnstile) return
        widgetId = window.turnstile.render(ref.current, {
          sitekey: TURNSTILE_SITE_KEY,
          theme: "dark",
          callback: (t) => onToken(t),
          "expired-callback": () => onToken(null),
          "error-callback": () => onToken(null),
        })
      })
      .catch(() => onToken(null))
    return () => {
      cancelled = true
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId)
    }
  }, [onToken])

  if (!TURNSTILE_SITE_KEY) return null
  return <div ref={ref} className="min-h-[65px]" />
}

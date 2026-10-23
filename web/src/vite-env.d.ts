/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  // Cloudflare Turnstile site key (public). Unset = no widget rendered.
  readonly VITE_TURNSTILE_SITE_KEY?: string
}

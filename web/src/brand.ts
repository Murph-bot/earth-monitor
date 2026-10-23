// The product name lives here and only here. index.html and public/404.html
// get it at build time (vite.config.ts replaces %BRAND% tokens).
export const BRAND = "Ombria"
export const BRAND_SUBTITLE = "όμβρος = rain"
export const TAGLINE = BRAND_SUBTITLE
export const REGIONS_LABEL = "Thessaly & Attica"
export const LANDING_TITLE = `${BRAND} — weekly greenness & rain for ${REGIONS_LABEL} fields`
export const pageTitle = (page?: string) => (page ? `${page} — ${BRAND}` : LANDING_TITLE)
// Absolute: crawlers ignore relative og:image (og:url is omitted so previews
// don't claim production). Swap when the domain is cleared.
export const SITE_URL = "https://earth-monitor.pages.dev"

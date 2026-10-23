import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import { BRAND, BRAND_SUBTITLE, TAGLINE, LANDING_TITLE, REGIONS_LABEL, SITE_URL } from "./src/brand";

// One brand constant (src/brand.ts) for the static HTML too: %BRAND%-style
// tokens in index.html (transformIndexHtml) and public/404.html (rewritten in
// dist after the copy, since Vite copies public/ verbatim).
// absolute og:/twitter:image needs a *stable* origin (CF_PAGES_URL is the
// per-deploy hash URL). Pages production branch → SITE_URL; other branches →
// the branch alias (lowercase, non-alnum → "-", max 28 chars); else SITE_URL.
const PROD_BRANCH = "main";
const PAGES_PROJECT = "earth-monitor";
export const branchAlias = (b: string) =>
  b.toLowerCase().replace(/[^a-z0-9]/g, "-").slice(0, 28).replace(/^-+|-+$/g, "");
const ogOrigin = () => {
  const b = process.env.CF_PAGES_BRANCH;
  const origin =
    process.env.CF_PAGES && b && b !== PROD_BRANCH && branchAlias(b)
      ? `https://${branchAlias(b)}.${PAGES_PROJECT}.pages.dev`
      : SITE_URL;
  return origin.replace(/\/+$/, "");
};

const tokens: Record<string, string> = {
  "%BRAND%": BRAND,
  "%BRAND_SUBTITLE%": BRAND_SUBTITLE,
  "%TAGLINE%": TAGLINE,
  "%LANDING_TITLE%": LANDING_TITLE,
  "%REGIONS%": REGIONS_LABEL,
  "%SITE_URL%": SITE_URL,
  "%ORIGIN%": ogOrigin(),
};
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const fill = (html: string) =>
  Object.entries(tokens).reduce((h, [k, v]) => h.split(k).join(esc(v)), html);

const brandHtml = (): Plugin => {
  let outDir = "dist";
  return {
    name: "brand-html",
    configResolved(c) {
      outDir = resolve(c.root, c.build.outDir);
    },
    transformIndexHtml: fill,
    closeBundle() {
      const p = resolve(outDir, "404.html");
      if (existsSync(p)) writeFileSync(p, fill(readFileSync(p, "utf8")));
    },
  };
};

export default defineConfig({
  plugins: [react(), tailwindcss(), brandHtml()],
  server: {
    // API stays on uvicorn; the browser only ever sees same-origin /v1
    proxy: { "/v1": "http://127.0.0.1:8000" },
  },
});

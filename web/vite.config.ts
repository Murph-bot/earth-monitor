import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // API stays on uvicorn; the browser only ever sees same-origin /v1
    proxy: { "/v1": "http://127.0.0.1:8000" },
  },
});

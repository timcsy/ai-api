import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend dev server URL. Override at runtime: `BACKEND_URL=http://localhost:47821 npm run dev`
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: (() => {
      // Browser navigations (Accept: text/html) for paths that overlap SPA
      // routes (`/admin`, `/catalog`) must serve index.html so React Router
      // takes over. Only XHR / fetch (application/json etc.) goes to backend.
      const bypassHtml = {
        target: BACKEND,
        bypass: (req: { headers: Record<string, string | string[] | undefined> }) => {
          const accept = req.headers.accept;
          const acceptStr = Array.isArray(accept) ? accept.join(",") : (accept ?? "");
          if (acceptStr.includes("text/html")) return "/index.html";
        },
      };
      return {
        "/health": BACKEND,
        "/auth": BACKEND,
        "/me": BACKEND,
        "/admin": bypassHtml,
        "/catalog": bypassHtml,
        "/v1": BACKEND,
      };
    })(),
  },
});

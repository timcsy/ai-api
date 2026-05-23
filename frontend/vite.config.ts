import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/health": BACKEND,
      "/auth": BACKEND,
      "/me": BACKEND,
      "/admin": BACKEND,
      "/catalog": BACKEND,
      "/v1": BACKEND,
    },
  },
});

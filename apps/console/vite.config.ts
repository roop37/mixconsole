import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `pnpm dev` proxies the API to a local `mixconsole serve` (default port 8765); the built app is
// served by `mixconsole serve --ui` from the same origin, so no CORS and no external hosts.
const api = process.env.MIXCONSOLE_API ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", sourcemap: false, target: "es2022", chunkSizeWarningLimit: 700 },
  server: { host: "127.0.0.1", proxy: { "/api": { target: api, changeOrigin: false } } },
  test: { include: ["tests/**/*.test.ts"], environment: "node" },
});

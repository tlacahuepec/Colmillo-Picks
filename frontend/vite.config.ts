import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/picks": "http://localhost:8000",
      "/slates": "http://localhost:8000",
      "/catalog": "http://localhost:8000",
      "/diagnostics": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
      "/version": "http://localhost:8000",
      "/matches": "http://localhost:8000",
      "/enrichment": "http://localhost:8000",
      "/stats": "http://localhost:8000",
      "/availability": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
  },
});

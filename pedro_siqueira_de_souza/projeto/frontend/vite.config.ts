import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend Vite + React. O proxy encaminha /api e /health para o
// backend FastAPI (porta 8000), evitando CORS no dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The proxy routes /api to the Express server and / to this Vite dev server.
// In local dev we proxy /api to the api-server so relative fetch("/api/...")
// works without hardcoding ports.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_TARGET ?? "http://localhost:80",
        changeOrigin: true,
      },
    },
  },
});

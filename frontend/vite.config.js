import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend origin for the dev proxy. docker-compose sets VITE_API_URL=http://backend:5000.
const API = process.env.VITE_API_URL ?? "http://127.0.0.1:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api":  { target: API, changeOrigin: true },
      "/auth": { target: API, changeOrigin: true },
      "/socket.io": { target: API, ws: true, changeOrigin: true },
    },
  },
});

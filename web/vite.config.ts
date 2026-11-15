import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API so the browser uses same-origin requests (as in Docker/nginx).
const api = process.env.HMT_API ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { output: { manualChunks: { charts: ["recharts"], react: ["react", "react-dom", "react-router-dom"] } } },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: api, changeOrigin: true, ws: true },
    },
  },
});

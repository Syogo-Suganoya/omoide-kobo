import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const target = process.env.API_PROXY_TARGET ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // コンテナ内のバインドマウントでは inotify が効かないことがある
    watch: { usePolling: true, interval: 300 },
    proxy: {
      "/api": { target, changeOrigin: true },
      "/healthz": { target, changeOrigin: true },
    },
  },
});

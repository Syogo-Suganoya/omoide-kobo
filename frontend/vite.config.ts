import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const target = process.env.API_PROXY_TARGET ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // 同じ compose 内から `http://web:5173` で開けるようにする（画面の写しを撮る shots）。
    // 開発サーバーだけの設定で、本番は静的ファイルを配るので関係しない。
    allowedHosts: ["web", "omoide-kobo.local", "localhost"],
    // コンテナ内のバインドマウントでは inotify が効かないことがある
    watch: { usePolling: true, interval: 300 },
    proxy: {
      "/api": { target, changeOrigin: true },
      "/healthz": { target, changeOrigin: true },
    },
  },
});

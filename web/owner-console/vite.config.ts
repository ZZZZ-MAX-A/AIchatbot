import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/healthz": {
        target: "http://127.0.0.1:8090",
        changeOrigin: true,
      },
      "/api/v1/owner-console": {
        target: "http://127.0.0.1:8090",
        changeOrigin: true,
      },
    },
  },
});

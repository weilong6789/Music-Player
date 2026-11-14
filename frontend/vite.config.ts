import { defineConfig } from "vite";

export default defineConfig({
  // Verovio's WASM is one 8 MB chunk, loaded only when a score is opened.
  build: { chunkSizeWarningLimit: 9000 },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // "/src" là đường dẫn root-absolute của Vite → khỏi cần node:url/@types/node.
    alias: {
      "@": "/src",
    },
  },
  server: {
    port: 5173,
    // Fail thẳng nếu 5173 bận, KHÔNG tự nhảy 5174 (tránh lệch origin -> backend CORS 400).
    strictPort: true,
  },
});

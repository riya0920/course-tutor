import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: forward API calls to the FastAPI backend so the frontend can use
// same-origin relative URLs in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      "/upload": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/quiz": "http://localhost:8000",
      "/progress": "http://localhost:8000",
      "/explain": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});

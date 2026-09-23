import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the React app calls /api/*, proxied to FastAPI on :8000. Prod: same origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});

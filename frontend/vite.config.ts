import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    // In development the browser talks to Vite, which forwards API calls to FastAPI.
    proxy: { "/api": "http://localhost:8000" },
  },
});

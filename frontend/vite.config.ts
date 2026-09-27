import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // In development the frontend is served by Vite with hot reload, and its API calls go to the
  // web server (`make web`), which adds the credentials, exactly as in production.
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/bff": "http://localhost:8080",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    // The styles play no part in what the tests check, and Tailwind would compile them for every file.
    css: false,
  },
});

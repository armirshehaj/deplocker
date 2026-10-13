import { defineConfig } from "vitest/config";
import path from "path";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  define: {
    API_URL: JSON.stringify("/api"),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: [
      "src/test/unit/**/*.test.{ts,tsx}",
      "src/test/integration/**/*.test.{ts,tsx}",
      "src/test/e2e/**/*.test.{ts,tsx}",
    ],
  },
});

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 300_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
  },
  outputDir: "../data/web_preview/test-results",
});

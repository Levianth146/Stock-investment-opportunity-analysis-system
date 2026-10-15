/**
 * Config riêng cho e2e live (LLM thật).
 * Không dùng testIgnore/grepInvert của config mặc định.
 * Không gắn quota assert teardown — live test được phép đổi quota/budget.
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e/live",
  timeout: 360_000,
  globalSetup: "./e2e/live-global-setup.ts",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
  },
  outputDir: "../data/web_preview/test-results-live",
});

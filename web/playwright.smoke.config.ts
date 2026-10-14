/**
 * Config riêng cho smoke.spec.ts (bộ ảnh @slow).
 * Không kế thừa testIgnore của config mặc định.
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  testMatch: "smoke.spec.ts",
  timeout: 90_000,
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
  },
  outputDir: "../data/web_preview/test-results-smoke",
});

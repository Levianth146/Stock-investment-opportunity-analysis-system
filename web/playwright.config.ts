import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  // Suite mặc định: không live LLM, không bộ ảnh @slow (mục tiêu < 90s)
  testIgnore: ["**/live/**", "**/smoke.spec.ts"],
  grepInvert: /@live|@slow/,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
  },
  outputDir: "../data/web_preview/test-results",
});

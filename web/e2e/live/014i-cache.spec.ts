/**
 * @live — đọc cache AI sau khi chạy LLM thật, sẽ phụ thuộc quota/cache thật.
 * Chạy riêng: npm run test:e2e:live
 */
import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../data/web_preview",
);

async function failOnConsole(page: Page) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      throw new Error(`Console error: ${msg.text()}`);
    }
  });
}

test.describe("014i AI label from live cache @live", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  for (const [symbol, modelHint] of [
    ["FPT", "glm"],
    ["MWG", "gemini"],
  ] as const) {
    test(`${symbol} shows AI model after live LLM @live`, async ({ page }) => {
      test.setTimeout(120_000);
      await failOnConsole(page);
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(`/t/${symbol}`);
      await expect(page.getByRole("heading", { name: new RegExp(symbol, "i") })).toBeVisible({
        timeout: 60_000,
      });
      const debateHeading = page.getByRole("heading", {
        name: /Luận điểm thuận \/ nghịch/i,
      });
      await debateHeading.scrollIntoViewIfNeeded();
      await expect(debateHeading).toBeVisible({ timeout: 30_000 });
      const badge = page.getByTestId("debate-source-label");
      await badge.scrollIntoViewIfNeeded();
      await expect(badge).toContainText(/Nguồn:\s*AI/i, { timeout: 30_000 });
      await expect(badge).toContainText(new RegExp(modelHint, "i"));
      const box = await debateHeading.boundingBox();
      await page.screenshot({
        path: path.join(outDir, `014i-${symbol}-ai-label.png`),
        clip: box
          ? { x: 0, y: Math.max(0, box.y - 8), width: 1280, height: 520 }
          : undefined,
      });
    });
  }
});

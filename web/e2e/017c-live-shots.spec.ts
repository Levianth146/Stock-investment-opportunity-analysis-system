/**
 * Chụp ảnh live (API thật) cho báo cáo 017c — không mock income-flow.
 */
import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../data/web_preview",
);

test.describe("017c live shots", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  test("FPT HPG AAM ACB live", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1280, height: 800 });

    for (const [sym, file] of [
      ["FPT", "017c-live-FPT-1280.png"],
      ["HPG", "017c-live-HPG-1280.png"],
      ["AAM", "017c-live-AAM-loss-1280.png"],
      ["ACB", "017c-live-ACB-bank-1280.png"],
    ] as const) {
      await page.goto(`/t/${sym}?tab=growth`);
      await expect(page.getByRole("heading", { name: new RegExp(sym, "i") })).toBeVisible({
        timeout: 60_000,
      });
      await page.getByRole("tab", { name: "Tăng trưởng" }).click();
      await expect(page.locator(".income-flow")).toBeVisible({ timeout: 30_000 });
      if (sym === "ACB") {
        await expect(page.getByText("Chưa hỗ trợ ngân hàng")).toBeVisible();
      } else {
        if (sym === "AAM") {
          const y2024 = page.locator(".income-flow-year-chip", { hasText: "2024" });
          if (await y2024.count()) await y2024.click();
        } else {
          const yLatest = page.locator(".income-flow-year-chip").last();
          if (await yLatest.count()) await yLatest.click();
        }
        await expect(
          page.locator(".income-flow-svg, .income-flow-bars, .empty").first(),
        ).toBeVisible({ timeout: 30_000 });
      }
      await page.screenshot({ path: path.join(outDir, file), fullPage: false });
    }

    // FPT dark + 360
    await page.goto("/t/FPT?tab=growth");
    await expect(page.locator(".income-flow")).toBeVisible({ timeout: 60_000 });
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    await page.screenshot({
      path: path.join(outDir, "017c-live-FPT-dark-1280.png"),
      fullPage: false,
    });
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));
    await page.setViewportSize({ width: 360, height: 740 });
    await expect(page.locator(".income-flow-bars")).toBeVisible();
    await page.screenshot({
      path: path.join(outDir, "017c-live-FPT-360.png"),
      fullPage: true,
    });
  });
});

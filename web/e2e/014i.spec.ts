import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../data/web_preview",
);

async function failOnConsole(page: Page) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      throw new Error(`Console error: ${msg.text()}`);
    }
  });
}

test.describe("014i live AI button", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  for (const symbol of ["FPT", "HPG"] as const) {
    test(`click Tạo lại bằng AI — ${symbol}`, async ({ page }) => {
      test.setTimeout(360_000);
      await failOnConsole(page);
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(`/t/${symbol}`);
      await expect(page.getByRole("heading", { name: new RegExp(symbol, "i") })).toBeVisible({
        timeout: 60_000,
      });
      await expect(page.getByText(/Luận điểm thuận \/ nghịch/i)).toBeVisible({
        timeout: 30_000,
      });
      await page.screenshot({
        path: path.join(outDir, `014i-${symbol}-before.png`),
        fullPage: false,
      });

      const btn = page.getByRole("button", { name: /Tạo lại bằng AI/i });
      const disabled = await btn.isDisabled().catch(() => true);
      if (disabled) {
        await page.screenshot({
          path: path.join(outDir, `014i-${symbol}-after-disabled.png`),
          fullPage: false,
        });
        // Circuit/quota — vẫn chụp; không fail cứng nếu API báo tạm nghỉ
        test.info().annotations.push({
          type: "note",
          description: "Nút AI đang disabled (circuit/quota)",
        });
        return;
      }
      await btn.click();
      await expect(page.getByText(/Đang tạo|AI ·|Chỉ số — AI|Hết hạn|tạm nghỉ/i)).toBeVisible({
        timeout: 30_000,
      });
      // Chờ xong (tối đa ~3 phút)
      await expect(btn).toBeEnabled({ timeout: 240_000 });
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(outDir, `014i-${symbol}-after.png`),
        fullPage: false,
      });
    });
  }
});

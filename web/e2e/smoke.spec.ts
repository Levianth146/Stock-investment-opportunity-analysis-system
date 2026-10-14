import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const rootPreview = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../data/web_preview",
);
const beforeDir = path.join(rootPreview, "before_014g");
const outDir = rootPreview;

async function failOnConsole(page: Page) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      throw new Error(`Console error: ${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => {
    throw new Error(`Page error: ${err.message}`);
  });
}

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.evaluate((t) => {
    localStorage.setItem("stockai-theme", t);
    document.documentElement.setAttribute("data-theme", t);
  }, theme);
  const btn = page.getByRole("button", { name: /Giao diện/i });
  for (let i = 0; i < 4; i++) {
    const mode = await page.evaluate(() =>
      document.documentElement.getAttribute("data-theme"),
    );
    if (mode === theme) break;
    await btn.click();
  }
  await page.evaluate((t) => {
    localStorage.setItem("stockai-theme", t);
    document.documentElement.setAttribute("data-theme", t);
  }, theme);
}

function archivePreviousScreenshots() {
  fs.mkdirSync(beforeDir, { recursive: true });
  fs.mkdirSync(outDir, { recursive: true });
  for (const name of fs.readdirSync(outDir)) {
    if (!name.endsWith(".png")) continue;
    const src = path.join(outDir, name);
    const dest = path.join(beforeDir, name);
    if (fs.existsSync(src) && fs.statSync(src).isFile()) {
      fs.copyFileSync(src, dest);
    }
  }
}

test.beforeAll(() => {
  archivePreviousScreenshots();
});

const PVT_TABS = [
  "Tổng quan",
  "Định giá",
  "Tăng trưởng",
  "Sức khỏe tài chính",
  "Cổ tức",
  "Kỹ thuật",
  "Tin tức",
] as const;

test.describe("014g screenshots", () => {
  test("home, PVT every tab, VCB overview+valuation light/dark 1280/360", async ({
    page,
  }) => {
    test.setTimeout(420_000);
    await failOnConsole(page);

    for (const theme of ["light", "dark"] as const) {
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto("/");
      await setTheme(page, theme);
      await page.reload();
      await expect(
        page.getByRole("heading", { name: /Bảng xếp hạng/i }),
      ).toBeVisible({ timeout: 30_000 });
      await expect(page.locator(".rank-row").first()).toBeVisible({
        timeout: 120_000,
      });
      await page.screenshot({
        path: path.join(outDir, `rankings-1280-${theme}.png`),
        fullPage: true,
      });
      await page.setViewportSize({ width: 360, height: 740 });
      await page.screenshot({
        path: path.join(outDir, `rankings-360-${theme}.png`),
        fullPage: true,
      });

      // PVT — mọi tab
      for (const w of [1280, 360] as const) {
        await page.setViewportSize({
          width: w,
          height: w === 1280 ? 800 : 740,
        });
        await page.goto("/t/PVT");
        await setTheme(page, theme);
        await page.reload();
        await expect(page.getByRole("heading", { name: /PVT/i })).toBeVisible({
          timeout: 60_000,
        });
        for (const tab of PVT_TABS) {
          await page.getByRole("tab", { name: tab }).click();
          await page.waitForTimeout(500);
          const slug = tab
            .toLowerCase()
            .normalize("NFD")
            .replace(/\p{M}/gu, "")
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "");
          await page.screenshot({
            path: path.join(outDir, `ticker-PVT-${slug}-${w}-${theme}.png`),
            fullPage: true,
          });
        }
      }

      // VCB overview + valuation
      for (const w of [1280, 360] as const) {
        await page.setViewportSize({
          width: w,
          height: w === 1280 ? 800 : 740,
        });
        await page.goto("/t/VCB");
        await setTheme(page, theme);
        await page.reload();
        await expect(page.locator("h1")).toContainText("VCB", {
          timeout: 90_000,
        });
        for (const tab of ["Tổng quan", "Định giá"] as const) {
          await page.getByRole("tab", { name: tab }).click();
          await page.waitForTimeout(600);
          const slug = tab === "Tổng quan" ? "tong-quan" : "dinh-gia";
          await page.screenshot({
            path: path.join(outDir, `ticker-VCB-${slug}-${w}-${theme}.png`),
            fullPage: true,
          });
        }
      }
    }
  });
});

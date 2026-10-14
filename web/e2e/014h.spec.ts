import { test, expect, type Page, type Route } from "@playwright/test";
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

async function mockLlm(page: Page, body: Record<string, unknown>) {
  await page.route("**/api/llm/status", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        asof: "2026-10-08",
        disclaimer: "test",
        ...body,
      }),
    });
  });
  await page.route("**/api/meta", async (route: Route) => {
    const res = await route.fetch();
    const json = await res.json();
    json.llm = { ...(json.llm || {}), ...body };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(json),
    });
  });
}

test.describe("014h", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  test("dividend tab with data (FPT) and empty-ish bank note", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    await failOnConsole(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/t/FPT?tab=dividend");
    await expect(page.getByRole("heading", { name: /FPT/i })).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole("tab", { name: "Cổ tức" }).click();
    await expect(
      page.getByRole("heading", {
        name: /Cổ tức tiền mặt theo năm|Chưa có dữ liệu cổ tức/i,
      }).or(page.locator(".fin-chart-title, .empty").filter({
        hasText: /Cổ tức tiền mặt theo năm|Chưa có dữ liệu cổ tức/i,
      })).first(),
    ).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: path.join(outDir, "014h-dividend-FPT-1280.png"),
      fullPage: true,
    });
  });

  test("LLM block states (mock)", async ({ page }) => {
    test.setTimeout(90_000);
    await failOnConsole(page);

    await mockLlm(page, {
      state: "quota_blocked",
      key_configured: true,
      blocked_until: "2026-10-14T23:59:58+00:00",
      model: "gemini-3.8-flash",
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/t/PVT");
    await expect(page.getByRole("heading", { name: /PVT/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText("Hết hạn mức AI", { exact: false })).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole("button", { name: "Tạo lại bằng AI" }),
    ).toBeDisabled();
    await page.screenshot({
      path: path.join(outDir, "014h-llm-quota-blocked.png"),
      fullPage: false,
    });

    await page.unroute("**/api/llm/status");
    await page.unroute("**/api/meta");
    await mockLlm(page, {
      state: "no_key",
      key_configured: false,
      blocked_until: null,
    });
    await page.reload();
    await expect(page.getByText("Chưa cấu hình AI", { exact: true })).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole("button", { name: "Tạo lại bằng AI" }),
    ).toHaveCount(0);
    await page.screenshot({
      path: path.join(outDir, "014h-llm-no-key.png"),
      fullPage: false,
    });

    await page.unroute("**/api/llm/status");
    await page.unroute("**/api/meta");
    await mockLlm(page, {
      state: "ok",
      key_configured: true,
      blocked_until: null,
      model: "gemini-3.6-flash",
    });
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Tạo lại bằng AI" }),
    ).toBeEnabled({ timeout: 30_000 });
    await expect(page.getByTestId("debate-source-label")).toBeVisible();
    await expect(page.getByTestId("debate-source-label")).toContainText(
      /Tự động từ chỉ số|AI ·/i,
    );
    await page.screenshot({
      path: path.join(outDir, "014h-llm-ok.png"),
      fullPage: false,
    });
  });

  test("52w bar + quarterly charts at 360px", async ({ page }) => {
    test.setTimeout(90_000);
    await failOnConsole(page);
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto("/t/PVT?tab=valuation");
    await expect(page.getByRole("heading", { name: /PVT/i })).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole("tab", { name: "Định giá" }).click();
    await expect(
      page.locator(".fin-chart-title").filter({
        hasText: "Vị trí giá trong biên 52 tuần",
      }),
    ).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: path.join(outDir, "014h-52w-PVT-360.png"),
      fullPage: true,
    });

    await page.getByRole("tab", { name: "Tăng trưởng" }).click();
    // Sau 014i: tách thành hai biểu đồ (không còn «Doanh thu & LNST theo quý»)
    await expect(
      page.locator(".fin-chart-title").filter({
        hasText: "Doanh thu theo quý (tỷ đồng)",
      }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator(".fin-chart-title").filter({
        hasText: "LNST theo quý (tỷ đồng)",
      }),
    ).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: path.join(outDir, "014h-quarterly-PVT-360.png"),
      fullPage: true,
    });
  });
});

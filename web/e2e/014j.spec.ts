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

test.describe("014j non-blocking AI jobs", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  test("click → Đang tạo → result (mock delay 3s)", async ({ page }) => {
    test.setTimeout(120_000);
    await failOnConsole(page);
    await page.setViewportSize({ width: 1280, height: 900 });

    const jobId = "e2e014jjob01";
    let createdAt = 0;
    let polled = 0;

    await page.route("**/api/llm/status", async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          asof: "2026-10-08",
          disclaimer: "x",
          state: "ok",
          provider: "mock",
          model: "mock-flash",
          key_configured: true,
        }),
      });
    });

    await page.route("**/api/tickers/FPT/debate/jobs*", async (route: Route) => {
      const req = route.request();
      const url = req.url();
      if (req.method() === "POST" && !url.includes(jobId)) {
        createdAt = Date.now();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            asof: "2026-10-08",
            disclaimer: "x",
            job_id: jobId,
            state: "queued",
            symbol: "FPT",
            profile: "long_term",
            attempt: 0,
          }),
        });
        return;
      }
      if (req.method() === "GET" && url.includes(jobId)) {
        polled += 1;
        const elapsed = Date.now() - createdAt;
        if (elapsed < 3000) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              asof: "2026-10-08",
              disclaimer: "x",
              job_id: jobId,
              state: "running",
              symbol: "FPT",
              profile: "long_term",
              attempt: 1,
            }),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            asof: "2026-10-08",
            disclaimer: "x",
            job_id: jobId,
            state: "ok",
            symbol: "FPT",
            profile: "long_term",
            attempt: 1,
            result: {
              asof: "2026-10-08",
              disclaimer: "x",
              source: "LLM",
              model: "mock-flash",
              created_at: "2026-10-14T12:00:00Z",
              bull: [{ text: "Thuận mock E2E.", refs: ["m2.roe"] }],
              bear: [{ text: "Nghịch mock E2E.", refs: ["m6.beta"] }],
              ai_attempt: { state: "ok" },
            },
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/t/FPT");
    await expect(page.getByRole("heading", { name: /FPT/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText(/Luận điểm thuận \/ nghịch/i)).toBeVisible({
      timeout: 30_000,
    });

    const btn = page.getByRole("button", { name: /Tạo lại bằng AI/i });
    await page.screenshot({
      path: path.join(outDir, "014j-btn-idle.png"),
      fullPage: false,
    });
    await btn.click();
    await expect(
      page.getByRole("button", { name: /Đang tạo/i }),
    ).toBeVisible({ timeout: 10_000 });
    await page.screenshot({
      path: path.join(outDir, "014j-btn-creating.png"),
      fullPage: false,
    });
    // Trang vẫn dùng được — tab khác còn click được
    await expect(page.getByRole("tab", { name: /Định giá|Cổ tức|Tăng trưởng/i }).first()).toBeVisible();

    await expect(page.getByText(/Thuận mock E2E/i)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/AI · mock-flash/i)).toBeVisible();
    await page.screenshot({
      path: path.join(outDir, "014j-btn-done.png"),
      fullPage: false,
    });
    expect(polled).toBeGreaterThan(0);
  });
});

import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import { attachHttpErrorLog, flushHttpErrorLog } from "./helpers/httpLog";

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

  test("click → Đang tạo → result (mock delay 3s)", async ({ page }, testInfo) => {
    test.setTimeout(90_000);
    const httpErrors = attachHttpErrorLog(page, testInfo);
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

    // Mock toàn bộ /debate/jobs* — không continue() về API thật (tránh 404 job giả)
    await page.route("**/api/tickers/FPT/debate/jobs**", async (route: Route) => {
      const req = route.request();
      const url = req.url();
      if (req.method() === "POST") {
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
      // GET job id lạ / method khác → 404 có chủ đích trong mock (không hit API)
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          asof: "2026-10-08",
          disclaimer: "x",
          error: `Mock: không có job cho ${url}`,
        }),
      });
    });

    try {
      await page.goto("/t/FPT");
      await expect(page.getByRole("heading", { name: /FPT/i })).toBeVisible({
        timeout: 60_000,
      });
      await expect(
        page.getByRole("heading", { name: /Luận điểm thuận \/ nghịch/i }),
      ).toBeVisible({ timeout: 30_000 });

      const btn = page.getByTestId("debate-ai-btn");
      await page.screenshot({
        path: path.join(outDir, "014j-btn-idle.png"),
        fullPage: false,
      });
      await btn.click();
      await expect(page.getByTestId("debate-ai-btn")).toHaveText(/Đang tạo/i, {
        timeout: 10_000,
      });
      await expect(page.getByTestId("debate-source-label")).toContainText(
        /Đang tạo bằng AI/i,
      );
      await expect(page.getByTestId("debate-fail-line")).toHaveCount(0);
      await page.screenshot({
        path: path.join(outDir, "014j-btn-creating.png"),
        fullPage: false,
      });
      await expect(
        page.getByRole("tab", { name: /Định giá|Cổ tức|Tăng trưởng/i }).first(),
      ).toBeVisible();

      await expect(page.getByText("Thuận mock E2E.", { exact: true })).toBeVisible({
        timeout: 30_000,
      });
      await expect(page.getByTestId("debate-source-label")).toContainText(
        /AI · mock-flash/i,
      );
      await page.screenshot({
        path: path.join(outDir, "014j-btn-done.png"),
        fullPage: false,
      });
      expect(polled).toBeGreaterThan(0);
      // Mọi status >=400 đã log qua attachHttpErrorLog; suite mock không được có 404
      expect(
        httpErrors,
        `Phát hiện HTTP >=400:\n${httpErrors.join("\n") || "(không)"}`,
      ).toEqual([]);
    } finally {
      await flushHttpErrorLog(httpErrors, testInfo);
    }
  });

  test("idle → creating (xóa lỗi) → failed → creating lại", async ({
    page,
  }, testInfo) => {
    test.setTimeout(90_000);
    const httpErrors = attachHttpErrorLog(page, testInfo);
    await failOnConsole(page);
    await page.setViewportSize({ width: 1280, height: 900 });

    let mode: "fail" | "ok" = "fail";
    let jobSeq = 0;
    let createdAt = 0;

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

    await page.route("**/api/tickers/FPT/debate/jobs**", async (route: Route) => {
      const req = route.request();
      const url = req.url();
      if (req.method() === "POST") {
        jobSeq += 1;
        createdAt = Date.now();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            asof: "2026-10-08",
            disclaimer: "x",
            job_id: `job${jobSeq}`,
            state: "queued",
            symbol: "FPT",
            profile: "long_term",
            attempt: 0,
          }),
        });
        return;
      }
      const m = /\/debate\/jobs\/([^/?]+)/.exec(url);
      const id = m?.[1];
      if (req.method() === "GET" && id) {
        if (Date.now() - createdAt < 800) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              asof: "2026-10-08",
              disclaimer: "x",
              job_id: id,
              state: "running",
              symbol: "FPT",
              profile: "long_term",
              attempt: 1,
            }),
          });
          return;
        }
        if (mode === "fail") {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              asof: "2026-10-08",
              disclaimer: "x",
              job_id: id,
              state: "failed",
              symbol: "FPT",
              profile: "long_term",
              attempt: 1,
              reason_code: "all_providers_failed",
              result: {
                asof: "2026-10-08",
                disclaimer: "x",
                source: "TEMPLATE",
                bull: [{ text: "Thuận chỉ số.", refs: [] }],
                bear: [{ text: "Nghịch chỉ số.", refs: [] }],
                ai_attempt: {
                  state: "failed",
                  reason_code: "all_providers_failed",
                },
              },
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
            job_id: id,
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
              bull: [{ text: "Thuận sau retry.", refs: [] }],
              bear: [{ text: "Nghịch sau retry.", refs: [] }],
              ai_attempt: { state: "ok" },
            },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ error: `Mock miss ${url}` }),
      });
    });

    try {
      await page.goto("/t/FPT");
      await expect(page.getByRole("heading", { name: /FPT/i })).toBeVisible({
        timeout: 60_000,
      });
      const btn = page.getByTestId("debate-ai-btn");
      await expect(btn).toBeEnabled({ timeout: 30_000 });

      const debateHeading = page.getByRole("heading", {
        name: /Luận điểm thuận \/ nghịch/i,
      });
      const shotDebate = async (name: string) => {
        await debateHeading.scrollIntoViewIfNeeded();
        const box = await debateHeading.boundingBox();
        await page.screenshot({
          path: path.join(outDir, name),
          clip: box
            ? {
                x: Math.max(0, box.x - 8),
                y: Math.max(0, box.y - 8),
                width: Math.min(1280, box.width + 48),
                height: 280,
              }
            : undefined,
        });
      };

      await debateHeading.scrollIntoViewIfNeeded();
      await btn.click();
      await expect(page.getByTestId("debate-source-label")).toContainText(
        /Đang tạo bằng AI/i,
      );
      await expect(page.getByTestId("debate-fail-line")).toHaveCount(0);
      await shotDebate("014k-btn-creating-clear.png");

      await expect(page.getByTestId("debate-fail-line")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("debate-fail-line")).toContainText(
        /AI không tạo được lần này/i,
      );
      await expect(page.getByTestId("debate-retry-btn")).toBeVisible();
      // Một dòng lỗi — không nhân đôi trên badge
      await expect(page.getByTestId("debate-source-label")).not.toContainText(
        /AI không tạo được/i,
      );
      await shotDebate("014k-btn-failed.png");

      mode = "ok";
      await page.getByTestId("debate-retry-btn").click();
      await expect(page.getByTestId("debate-fail-line")).toHaveCount(0);
      await expect(page.getByTestId("debate-source-label")).toContainText(
        /Đang tạo bằng AI/i,
      );
      await shotDebate("014k-btn-retry-creating.png");

      await expect(page.getByText("Thuận sau retry.", { exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("debate-source-label")).toContainText(
        /AI · mock-flash/i,
      );

      expect(httpErrors.filter((l) => l.startsWith("404"))).toEqual([]);
    } finally {
      await flushHttpErrorLog(httpErrors, testInfo);
    }
  });
});

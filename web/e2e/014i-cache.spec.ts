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

/** Mock GET/POST debate trả cache AI giả — không gọi LLM. */
async function mockAiDebateCache(
  page: Page,
  symbol: string,
  model: string,
  createdAt: string,
) {
  await page.route("**/api/llm/status", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        asof: "2026-10-08",
        disclaimer: "test",
        state: "ok",
        provider: "mock",
        model,
        key_configured: true,
      }),
    });
  });

  await page.route(
    `**/api/tickers/${symbol}/debate**`,
    async (route: Route) => {
      const url = route.request().url();
      // Không nuốt /debate/jobs*
      if (url.includes("/debate/jobs")) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          asof: "2026-10-08",
          disclaimer: "test",
          source: "CACHE",
          model,
          created_at: createdAt,
          bull: [{ text: "Thuận từ cache mock.", refs: ["m2.roe"] }],
          bear: [{ text: "Nghịch từ cache mock.", refs: ["m6.beta"] }],
          ai_attempt: { state: "ok" },
        }),
      });
    },
  );
}

test.describe("014i AI label from mocked cache", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  for (const [symbol, model] of [
    ["FPT", "mock-glm"],
    ["MWG", "mock-gemini"],
  ] as const) {
    test(`${symbol} shows AI · model · ngày (mock cache)`, async ({ page }) => {
      test.setTimeout(90_000);
      await failOnConsole(page);
      await mockAiDebateCache(page, symbol, model, "2026-10-14T12:00:00Z");
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
      await expect(badge).toContainText(new RegExp(`AI · ${model}`, "i"), {
        timeout: 30_000,
      });
      // dateVi → DD/MM/YYYY (= «giờ» đã format)
      await expect(badge).toContainText(/14\/10\/2026/);

      const box = await debateHeading.boundingBox();
      await page.screenshot({
        path: path.join(outDir, `014i-${symbol}-ai-label-mock.png`),
        clip: box
          ? { x: 0, y: Math.max(0, box.y - 8), width: 1280, height: 520 }
          : undefined,
      });
    });
  }
});

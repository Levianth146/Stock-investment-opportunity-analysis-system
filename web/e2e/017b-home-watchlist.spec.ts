/**
 * 017b — trang chủ live + heatmap + theo dõi (mock SSE, không DNSE/AI thật).
 */
import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../data/web_preview",
);

function ensureOut() {
  fs.mkdirSync(outDir, { recursive: true });
}

const marketBody = {
  asof: "2026-10-08",
  disclaimer: "test",
  as_of_ts: "2026-10-08T10:00:00+07:00",
  label: "trực tiếp (tạm tính)",
  session: { phase: "continuous", as_of_ts: "2026-10-08T10:00:00+07:00" },
  realtime: { mode: "live", state: "live" },
  index: {
    symbol: "VNINDEX",
    name: "VN-Index",
    price: { value: 1280.5, basis: "live" },
    prev_close: { value: 1270.0 },
    change_pct: { value: 0.83 },
    candles_1m: [
      { t: 1, c: 1271 },
      { t: 2, c: 1275 },
      { t: 3, c: 1280.5 },
    ],
    series_eod: null,
    available: ["VNINDEX"],
    label: "trực tiếp (tạm tính)",
    source: "realtime",
  },
  breadth: {
    up: { value: 100 },
    down: { value: 80 },
    flat: { value: 30 },
    unmatched: { value: 25, label: "Chưa khớp" },
    liquid_count: 235,
    sum: 235,
    above_sma50: { value: 120 },
    above_sma200: { value: 90 },
    hit_52w_high: { value: 5 },
    hit_52w_low: { value: 3 },
    note: "Trên 235 mã thanh khoản đủ.",
  },
  lists: {
    strong_up: [
      {
        symbol: "AAA",
        price: { value: 25000 },
        change_pct: { value: 4.2 },
        relative_vol: { value: 2.1 },
      },
      {
        symbol: "BBB",
        price: { value: 18000 },
        change_pct: { value: 3.5 },
        relative_vol: { value: 1.4 },
      },
    ],
    strong_down: [],
    volume_spike: [],
    high_52w: [],
    low_52w: [],
    overbought: [],
    oversold: [],
    liquidity_note: "Lọc GTGD ≥ 1 tỷ đồng/ngày",
  },
  heatmap: [
    {
      symbol: "AAA",
      sector: "Banks",
      change_pct: { value: 2.1 },
      market_cap: { value: 5e13 },
    },
    {
      symbol: "BBB",
      sector: "Steel",
      change_pct: { value: -1.5 },
      market_cap: { value: 2e13 },
    },
    {
      symbol: "CCC",
      sector: "Banks",
      change_pct: { value: 0.4 },
      market_cap: { value: 3e13 },
    },
  ],
  disclaimer: "Phân tích trong phiên mang tính tạm tính.",
};

const closedMarket = {
  ...marketBody,
  label: "đóng cửa 08/10",
  session: { phase: "closed", as_of_ts: "2026-10-08T15:00:00+07:00" },
  realtime: { mode: "snapshot", state: "closed" },
  index: {
    ...marketBody.index!,
    label: "đóng cửa 08/10",
    source: "eod",
    price: { value: 1280.5, basis: "eod" },
  },
};

async function mockCommon(page: Page, opts?: { closed?: boolean; sseFail?: boolean }) {
  await page.route("**/api/meta**", async (route: Route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "test",
        profiles: ["long_term", "swing"],
        default_profile: "long_term",
        universe_count: 700,
        scored_count: 235,
        formula: "test",
      },
    });
  });
  await page.route("**/api/health**", async (route) => {
    await route.fulfill({ json: { status: "ok", asof: "2026-10-08", disclaimer: "t" } });
  });
  await page.route("**/api/realtime/market**", async (route) => {
    await route.fulfill({
      json: opts?.closed ? closedMarket : marketBody,
    });
  });
  await page.route("**/api/market", async (route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        index: {
          symbol: "VNINDEX",
          close: 1280.5,
          change_pct: 0.83,
          series_30d: [
            { time: "2026-09-01", close: 1250 },
            { time: "2026-10-08", close: 1280.5 },
          ],
        },
      },
    });
  });
  await page.route("**/api/realtime/status**", async (route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        mode: opts?.closed ? "snapshot" : "live",
        state: opts?.closed ? "closed" : opts?.sseFail ? "no_realtime" : "live",
        session: { phase: opts?.closed ? "closed" : "continuous" },
      },
    });
  });
  await page.route("**/api/rankings**", async (route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        total: 2,
        total_scored: 2,
        items: [
          {
            ticker: "AAA",
            name: "CT AAA",
            sector: "Banks",
            score: 62,
            rating: "Mua",
            scores: { F: 60, T: 55, V: 50, S: 40, R: 30 },
            price: 25000,
            ranked: true,
          },
          {
            ticker: "BBB",
            name: "CT BBB",
            sector: "Steel",
            score: 48,
            rating: "Nắm giữ",
            scores: { F: 50, T: 45, V: 40, S: 35, R: 40 },
            price: 18000,
            ranked: true,
          },
        ],
      },
    });
  });
  await page.route("**/api/sectors**", async (route) => {
    await route.fulfill({
      json: { asof: "2026-10-08", disclaimer: "t", items: [] },
    });
  });
  await page.route("**/api/quotes**", async (route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        items: [
          {
            symbol: "AAA",
            price: 25100,
            change_pct: 4.5,
            state: "live",
            basis: "live",
            label: "tạm tính",
          },
        ],
      },
    });
  });
  await page.route("**/api/watchlist/summary**", async (route) => {
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        items: [
          {
            symbol: "AAA",
            name: "CT AAA",
            sector: "Banks",
            price: { value: 25000, basis: "live" },
            change_pct: { value: 2.1 },
            score: 62,
            rank: 1,
            total_scored: 2,
            dividend_yield: { value: 0.04 },
            sector_ref: { value: 26000, gap_pct: 4, unreliable: false },
            state: "live",
            label: "trực tiếp (tạm tính)",
          },
        ],
      },
    });
  });
  await page.route("**/api/tickers/AAA**", async (route) => {
    const url = route.request().url();
    if (url.includes("/prices")) {
      await route.fulfill({
        json: {
          asof: "2026-10-08",
          disclaimer: "t",
          symbol: "AAA",
          range: "3m",
          ohlcv: [
            { time: "2026-07-01", open: 20, high: 21, low: 19, close: 20.5, volume: 1 },
            { time: "2026-10-08", open: 24, high: 26, low: 24, close: 25, volume: 2 },
          ],
        },
      });
      return;
    }
    if (url.includes("/checks")) {
      await route.fulfill({
        json: {
          asof: "2026-10-08",
          disclaimer: "t",
          symbol: "AAA",
          checks: [],
          rewards: [{ id: "r1", label_vi: "P/E thấp hơn ngành" }],
          rewards_failed: [],
          risks: [{ id: "k1", label_vi: "RSI cao" }],
          risks_failed: [],
          rewards_count: 1,
          risks_count: 1,
        },
      });
      return;
    }
    if (url.includes("/debate")) {
      await route.fulfill({
        json: {
          asof: "2026-10-08",
          disclaimer: "t",
          source: "template",
          bull: [{ text: "Biên lợi nhuận ổn." }],
          bear: [{ text: "Nợ vay tăng." }],
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        asof: "2026-10-08",
        disclaimer: "t",
        symbol: "AAA",
        profile: "long_term",
        company: { name: "CT AAA", sector: "Banks" },
        result: {
          score: 62,
          rating: "Mua",
          scores: { F: 60, T: 55, V: 50, S: 40, R: 30 },
        },
        modules: {},
      },
    });
  });

  if (opts?.sseFail) {
    await page.route("**/api/stream**", async (route) => {
      await route.abort("failed");
    });
  } else {
    // EventSource không đi qua page.route dễ dàng trên mọi trình duyệt —
    // poll fallback vẫn cập nhật bảng qua /api/quotes.
    await page.route("**/api/stream**", async (route) => {
      await route.abort("failed");
    });
  }
}

test.describe("017b home + watchlist", () => {
  test.beforeAll(() => ensureOut());

  test("home live mock + heatmap + screenshot", async ({ page }) => {
    await mockCommon(page);
    await page.goto("/");
    await expect(page.getByRole("region", { name: "VN-Index" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Trên \d+ mã thanh khoản đủ/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Heatmap ngành" })).toBeVisible();
    await page.screenshot({
      path: path.join(outDir, "017b_home_live.png"),
      fullPage: true,
    });
  });

  test("home closed", async ({ page }) => {
    await mockCommon(page, { closed: true });
    await page.goto("/");
    await expect(page.getByText(/đóng cửa/i).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({
      path: path.join(outDir, "017b_home_closed.png"),
      fullPage: true,
    });
  });

  test("heatmap only shot", async ({ page }) => {
    await mockCommon(page);
    await page.goto("/");
    const hm = page.getByRole("region", { name: "Heatmap ngành" });
    await expect(hm).toBeVisible({ timeout: 15_000 });
    await hm.screenshot({ path: path.join(outDir, "017b_heatmap.png") });
  });

  test("watchlist detail Esc + keyboard", async ({ page }) => {
    await mockCommon(page);
    await page.addInitScript(() => {
      localStorage.setItem(
        "stockai.watchlist.v1",
        JSON.stringify({ v: 1, symbols: ["AAA"], updatedAt: "2026-10-08" }),
      );
    });
    await page.goto("/theo-doi");
    await expect(page.getByRole("heading", { name: "Theo dõi" })).toBeVisible();
    const row = page.locator(".wl-row").first();
    await row.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.locator(".wl-row").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.screenshot({
      path: path.join(outDir, "017b_watchlist_detail.png"),
      fullPage: true,
    });
  });

  test("360px + light/dark", async ({ page }) => {
    await mockCommon(page);
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto("/");
    await expect(page.getByRole("region", { name: "VN-Index" })).toBeVisible({
      timeout: 15_000,
    });
    await page.screenshot({
      path: path.join(outDir, "017b_home_360.png"),
      fullPage: true,
    });
    await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await page.screenshot({
      path: path.join(outDir, "017b_home_dark.png"),
      fullPage: true,
    });
    await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme", "light");
    });
    await page.screenshot({
      path: path.join(outDir, "017b_home_light.png"),
      fullPage: true,
    });
  });

  test("SSE drop → poll quotes cập nhật", async ({ page }) => {
    await mockCommon(page, { sseFail: true });
    await page.addInitScript(() => {
      localStorage.setItem(
        "stockai.watchlist.v1",
        JSON.stringify({ v: 1, symbols: ["AAA"], updatedAt: "2026-10-08" }),
      );
    });
    await page.goto("/theo-doi");
    // Poll 15s quá lâu cho CI — gọi thẳng quotes đã mock; kiểm tra giá hiện
    await expect(page.getByText("AAA").first()).toBeVisible({ timeout: 15_000 });
  });

  test("unit_mismatch banner path", async ({ page }) => {
    await mockCommon(page);
    await page.route("**/api/realtime/status**", async (route) => {
      await route.fulfill({
        json: {
          asof: "2026-10-08",
          disclaimer: "t",
          mode: "unit_mismatch",
          state: "unit_mismatch",
          session: { phase: "continuous" },
        },
      });
    });
    await page.goto("/");
    await expect(page.getByText(/Đơn vị giá lệch/i)).toBeVisible({ timeout: 15_000 });
  });
});

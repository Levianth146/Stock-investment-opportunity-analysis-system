/**
 * 017c — Sankey luồng P&L trên tab Tăng trưởng (mock API).
 */
import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../data/web_preview",
);

function flowBody(period: string, opts?: { loss?: boolean; bank?: boolean }) {
  if (opts?.bank) {
    return {
      asof: "2026-10-08",
      disclaimer: "test",
      symbol: "ACB",
      period,
      unit: "billion_vnd",
      supported: false,
      message: "Chưa hỗ trợ ngân hàng",
      nodes: [],
      links: [],
      notes: [],
      available_periods: [],
    };
  }
  const loss = !!opts?.loss;
  const rev = 1000;
  const gp = 400;
  const nodes = loss
    ? [
        { id: "revenue", label: "Doanh thu", kind: "source", derived: false, value: rev, pct_revenue: 1 },
        { id: "gross_profit", label: "LN gộp", kind: "intermediate", derived: false, value: 75, pct_revenue: 0.075 },
        { id: "cogs", label: "Giá vốn", kind: "sink", derived: true, value: 160, pct_revenue: 0.16 },
        { id: "other_income", label: "Thu nhập khác (ròng)", kind: "other_income", derived: true, value: 35, pct_revenue: 0.035 },
        { id: "selling", label: "Chi phí bán hàng", kind: "sink", derived: false, value: 30, pct_revenue: 0.03 },
        { id: "admin", label: "Chi phí quản lý", kind: "sink", derived: false, value: 20, pct_revenue: 0.02 },
        { id: "interest", label: "Chi phí lãi vay", kind: "sink", derived: false, value: 5, pct_revenue: 0.005 },
        { id: "cit", label: "Thuế TNDN", kind: "sink", derived: true, value: 5, pct_revenue: 0.005 },
        { id: "loss", label: "Lỗ", kind: "loss", derived: false, value: 15, pct_revenue: 0.015 },
      ]
    : [
        { id: "revenue", label: "Doanh thu", kind: "source", derived: false, value: rev, pct_revenue: 1 },
        { id: "gross_profit", label: "LN gộp", kind: "intermediate", derived: false, value: gp, pct_revenue: 0.4 },
        { id: "cogs", label: "Giá vốn", kind: "sink", derived: true, value: 600, pct_revenue: 0.6 },
        { id: "selling", label: "Chi phí bán hàng", kind: "sink", derived: false, value: 50, pct_revenue: 0.05 },
        { id: "admin", label: "Chi phí quản lý", kind: "sink", derived: false, value: 50, pct_revenue: 0.05 },
        { id: "interest", label: "Chi phí lãi vay", kind: "sink", derived: false, value: 30, pct_revenue: 0.03 },
        { id: "cit", label: "Thuế TNDN", kind: "sink", derived: true, value: 40, pct_revenue: 0.04 },
        { id: "minority", label: "Cổ đông thiểu số", kind: "sink", derived: true, value: 20, pct_revenue: 0.02 },
        { id: "npat", label: "LNST cổ đông mẹ", kind: "sink", derived: false, value: 180, pct_revenue: 0.18 },
        { id: "other_balance", label: "Khác (cân đối)", kind: "derived", derived: true, value: 30, pct_revenue: 0.03 },
      ];
  const links = loss
    ? [
        { source: "revenue", target: "cogs", value: 160, pct_revenue: 0.16 },
        { source: "revenue", target: "gross_profit", value: 40, pct_revenue: 0.04 },
        { source: "other_income", target: "gross_profit", value: 35, pct_revenue: 0.035 },
        { source: "gross_profit", target: "selling", value: 30, pct_revenue: 0.03 },
        { source: "gross_profit", target: "admin", value: 20, pct_revenue: 0.02 },
        { source: "gross_profit", target: "interest", value: 5, pct_revenue: 0.005 },
        { source: "gross_profit", target: "cit", value: 5, pct_revenue: 0.005 },
        { source: "gross_profit", target: "loss", value: 15, pct_revenue: 0.015 },
      ]
    : [
        { source: "revenue", target: "cogs", value: 600, pct_revenue: 0.6 },
        { source: "revenue", target: "gross_profit", value: 400, pct_revenue: 0.4 },
        { source: "gross_profit", target: "selling", value: 50, pct_revenue: 0.05 },
        { source: "gross_profit", target: "admin", value: 50, pct_revenue: 0.05 },
        { source: "gross_profit", target: "interest", value: 30, pct_revenue: 0.03 },
        { source: "gross_profit", target: "cit", value: 40, pct_revenue: 0.04 },
        { source: "gross_profit", target: "minority", value: 20, pct_revenue: 0.02 },
        { source: "gross_profit", target: "npat", value: 180, pct_revenue: 0.18 },
        { source: "gross_profit", target: "other_balance", value: 30, pct_revenue: 0.03 },
      ];
  return {
    asof: "2026-10-08",
    disclaimer: "test",
    symbol: loss ? "AAM" : "FPT",
    period,
    unit: "billion_vnd",
    supported: true,
    revenue: rev,
    npat: loss ? -15 : 180,
    loss,
    nodes,
    links,
    notes: loss
      ? ["LNST < 0: nút «Lỗ» (màu rủi ro)."]
      : ["«Khác (cân đối)» là phần dư để bảo toàn luồng (phái sinh)."],
    conservation_ok: true,
    available_periods: ["2022", "2023", "2024", "TTM"],
    summary: {
      gross_margin: 0.4,
      net_margin: loss ? -0.015 : 0.18,
      expense_to_revenue: 0.13,
      gross_margin_prior: 0.38,
      net_margin_prior: 0.16,
      expense_to_revenue_prior: 0.14,
      prior_label: "kỳ trước",
    },
  };
}

async function mockIncomeFlow(page: Page, opts?: { loss?: boolean; bank?: boolean }) {
  await page.route("**/api/tickers/*/income-flow*", async (route: Route) => {
    const url = new URL(route.request().url());
    const period = url.searchParams.get("period") || "TTM";
    const sym = url.pathname.split("/")[3] || "FPT";
    const bank = opts?.bank || sym.toUpperCase() === "ACB";
    const loss = opts?.loss || sym.toUpperCase() === "AAM";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(flowBody(period, { loss, bank })),
    });
  });
}

async function gotoGrowth(page: Page, symbol: string) {
  await page.goto(`/t/${symbol}?tab=growth`);
  await expect(page.getByRole("heading", { name: new RegExp(symbol, "i") })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("tab", { name: "Tăng trưởng" }).click();
}

test.describe("017c income flow", () => {
  test.beforeAll(() => {
    fs.mkdirSync(outDir, { recursive: true });
  });

  test("year change + keyboard + light/dark + 360px", async ({ page }) => {
    test.setTimeout(120_000);
    await mockIncomeFlow(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoGrowth(page, "FPT");

    const section = page.locator(".income-flow");
    await expect(section.getByRole("heading", { name: /Luồng từ doanh thu/i })).toBeVisible({
      timeout: 30_000,
    });
    await expect(section.locator(".income-flow-svg")).toBeVisible();

    // Đổi năm bằng chip
    await section.locator(".income-flow-year-chip", { hasText: "2023" }).click();
    await expect(
      section.locator(".income-flow-year-chip.is-active"),
    ).toHaveText("2023", { timeout: 10_000 });

    // Slider + bàn phím
    const slider = section.locator("#income-flow-year");
    await slider.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(section.locator(".income-flow-year-chip.is-active")).toBeVisible();

    // TTM
    await section.locator(".income-flow-ttm").click();
    await expect(section.locator(".income-flow-ttm.is-active")).toBeVisible();

    // Focus nút SVG (tooltip)
    const firstNode = section.locator(".income-flow-svg rect").first();
    await firstNode.focus();
    await expect(section.locator(".income-flow-tooltip")).toBeVisible();

    await page.screenshot({
      path: path.join(outDir, "017c-FPT-sankey-light-1280.png"),
      fullPage: false,
    });

    // Dark
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    await page.screenshot({
      path: path.join(outDir, "017c-FPT-sankey-dark-1280.png"),
      fullPage: false,
    });
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));

    // 360px → thanh ngang theo %
    await page.setViewportSize({ width: 360, height: 740 });
    await expect(section.locator(".income-flow-bars")).toBeVisible();
    await expect(section.locator(".income-flow-svg")).toHaveCount(0);
    await page.screenshot({
      path: path.join(outDir, "017c-FPT-sankey-360.png"),
      fullPage: true,
    });
  });

  test("loss ticker + bank unsupported", async ({ page }) => {
    test.setTimeout(90_000);
    await mockIncomeFlow(page, { loss: true });
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoGrowth(page, "AAM");
    const section = page.locator(".income-flow");
    await expect(section.locator(".income-flow-label", { hasText: "Lỗ" })).toBeVisible({
      timeout: 30_000,
    });
    await page.screenshot({
      path: path.join(outDir, "017c-AAM-loss-1280.png"),
      fullPage: false,
    });

    await mockIncomeFlow(page, { bank: true });
    await gotoGrowth(page, "ACB");
    await expect(page.getByText("Chưa hỗ trợ ngân hàng")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: path.join(outDir, "017c-ACB-bank-unsupported.png"),
      fullPage: false,
    });
  });

  test("HPG profit screenshot", async ({ page }) => {
    test.setTimeout(90_000);
    await mockIncomeFlow(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await gotoGrowth(page, "HPG");
    await expect(page.locator(".income-flow .income-flow-svg")).toBeVisible({
      timeout: 30_000,
    });
    await page.screenshot({
      path: path.join(outDir, "017c-HPG-sankey-1280.png"),
      fullPage: false,
    });
  });
});

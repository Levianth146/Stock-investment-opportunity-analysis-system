import { describe, expect, it } from "vitest";
import {
  buildDividendSeries,
  formatDividendCell,
  summarizeDividends,
} from "./DividendCharts";
import type { FinancialPeriod } from "../api/types";

function row(
  period: string,
  dividends_paid: number | null,
  net_income_parent: number | null = 100e9,
): FinancialPeriod {
  return {
    period,
    items: { dividends_paid, net_income_parent },
    gross_margin: null,
    net_margin: null,
    roe: null,
    debt_to_equity: null,
    fcf: null,
  };
}

describe("DividendCharts", () => {
  it("null ≠ 0 in cells", () => {
    expect(formatDividendCell(null)).toBe("—");
    expect(formatDividendCell(0)).toBe("0");
  });

  it("API tỷ VND: 2742 → 2.742 tỷ (một lần đổi VND→tỷ)", () => {
    // 2_742_000_000_000 VND ÷ 1e9 = 2742 tỷ — API đã chia; format không chia lại
    expect(formatDividendCell(2_742_000_000_000 / 1e9)).toBe("2.742 tỷ");
    expect(formatDividendCell(2742)).toBe("2.742 tỷ");
  });

  it("all null/zero → empty summary", () => {
    const s = buildDividendSeries([
      row("2023", null),
      row("2024", 0),
      row("2025", null),
    ]);
    const sum = summarizeDividends(s);
    expect(sum.allNullOrZero).toBe(true);
    expect(sum.hasAny).toBe(false);
  });

  it("consecutive paid + avg payout", () => {
    const s = buildDividendSeries([
      row("2021", 10e9, 100e9),
      row("2022", 20e9, 100e9),
      row("2023", 0, 100e9),
      row("2024", 30e9, 100e9),
      row("2025", 40e9, 100e9),
    ]);
    const sum = summarizeDividends(s);
    expect(sum.consecutivePaid).toBe(2);
    expect(sum.avgPayout5y).toBeCloseTo(0.2, 5); // (0.1+0.2+0+0.3+0.4)/5 but 0 payout skipped when NI>0 and div=0 → ratio 0
  });

  it("implausible years excluded from streak/avg; ≥3/6 → unreliable", () => {
    const flagged = (period: string, div: number, ni: number): FinancialPeriod => ({
      ...row(period, div, ni),
      flags: ["dividends_implausible"],
    });
    const s = buildDividendSeries([
      flagged("2020", 1, 1e12),
      flagged("2021", 1, 1e12),
      flagged("2022", 1, 1e12),
      row("2023", 10, 100),
      row("2024", 20, 100),
      row("2025", 30, 100),
    ]);
    const sum = summarizeDividends(s);
    expect(sum.unreliable).toBe(true);
    expect(sum.consecutivePaid).toBe(3);
  });
});

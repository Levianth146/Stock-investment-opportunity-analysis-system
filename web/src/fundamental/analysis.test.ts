import { describe, expect, it } from "vitest";
import { narrateFundamental, ratiosOf, structureOf, type Period } from "./analysis";

const q = (i: number, ni: number): Period => ({
  period: `2025Q${i}`,
  items: {
    revenue: 1000e9, net_income_parent: ni, eps: 100, ebit: 200e9, interest_expense: 50e9,
    total_assets: 10000e9, total_equity: 4000e9, total_liabilities: 6000e9,
    current_assets: 6000e9, current_liabilities: 3000e9, cash: 1000e9, inventory: 2000e9,
    short_term_debt: 1000e9, long_term_debt: 500e9,
  },
});
const rows = [q(1, 100e9), q(2, 100e9), q(3, 100e9), q(4, 100e9)];

describe("fundamental", () => {
  it("structureOf tách tài sản/nguồn vốn, tổng khớp", () => {
    const s = structureOf(rows[3]!)!;
    expect(s.cash + s.inventory + s.otherCurrent + s.nonCurrentAssets).toBeCloseTo(s.totalAssets);
    expect(s.currentLiab + s.nonCurrentLiab + s.equity).toBeCloseTo(s.totalAssets);
    expect(s.debt).toBe(1500e9);
  });
  it("ratios: EPS TTM = tổng 4 quý, P/E theo giá", () => {
    const r = ratiosOf(rows, 2000, "live", 1e9);
    expect(r.epsTtm).toBe(400);
    expect(r.pe).toBeCloseTo(5);
    expect(r.bvps).toBeCloseTo(4000);
    expect(r.pb).toBeCloseTo(0.5);
    expect(r.roe).toBeCloseTo(10);
    expect(r.currentRatio).toBeCloseTo(2);
    expect(r.interestCover).toBeCloseTo(4);
  });
  it("thiếu quý → không bịa tỷ số", () => {
    const r = ratiosOf(rows.slice(0, 2), 2000, "eod", 1e9);
    expect(r.epsTtm).toBeNull();
    expect(r.pe).toBeNull();
  });
  it("diễn giải có so ngành và nhãn giá trực tiếp", () => {
    const r = ratiosOf(rows, 2000, "live", 1e9);
    const b = narrateFundamental({ s: structureOf(rows[3]!), prev: structureOf(rows[2]!), r, sectorPe: 12, sectorPb: 1.5, isFinancial: false });
    const all = b.map((x) => x.text).join(" ");
    expect(all).toMatch(/theo giá trực tiếp/);
    expect(all).toMatch(/thấp hơn trung vị ngành/);
    expect(b.map((x) => x.head)).toContain("Cơ cấu tài sản");
  });
});

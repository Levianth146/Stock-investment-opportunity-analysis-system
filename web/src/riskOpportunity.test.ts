import { describe, expect, it } from "vitest";
import type { TickerDetailResponse } from "./api/types";
import {
  RISK_OPP_NEUTRAL,
  asPctPoints,
  buildRiskOpportunity,
  componentOpportunities,
  componentRisks,
} from "./riskOpportunity";

function detail(partial: {
  scores?: TickerDetailResponse["result"]["scores"];
  m2?: Record<string, unknown>;
  m4?: Record<string, unknown>;
  m6?: Record<string, unknown>;
}): TickerDetailResponse {
  return {
    asof: "2026-10-08",
    disclaimer: "x",
    symbol: "AAA",
    profile: "long_term",
    company: { name: "A", sector: "Steel" },
    result: {
      ticker: "AAA",
      score: 50,
      rating: "Nắm giữ",
      scores: partial.scores ?? {
        F: 50,
        T: 50,
        V: 50,
        S: 50,
        R: 50,
      },
    },
    modules: {
      m2: { metrics: partial.m2 || {} },
      m4: { metrics: partial.m4 || {} },
      m6: { metrics: partial.m6 || {} },
    },
  };
}

describe("asPctPoints", () => {
  it("maps ratio and percent", () => {
    expect(asPctPoints(0.4)).toBe(40);
    expect(asPctPoints(40)).toBe(40);
    expect(asPctPoints(-0.35)).toBeCloseTo(-35);
  });
});

describe("component thresholds", () => {
  it("opportunity at >= 60, silent at 45–59, never says Trụ", () => {
    expect(componentOpportunities({ F: 60, T: 59, V: 45, S: 50, R: 50 })).toEqual([
      "Cơ bản 60,0.",
    ]);
    expect(componentOpportunities({ F: 59.9, T: 50, V: 50, S: 50, R: 50 })).toEqual(
      [],
    );
    const joined = componentOpportunities({
      F: 70,
      T: 80,
      V: 65,
      S: 90,
      R: 30,
    }).join(" ");
    expect(joined.toLowerCase()).not.toContain("trụ");
    expect(joined).toContain("Cơ bản");
    expect(joined).toContain("Kỹ thuật");
    expect(joined).toContain("Định giá");
    expect(joined).toContain("Tin tức");
    expect(joined).toContain("Rủi ro");
  });

  it("risk at < 45 for F/T/V/S; R risk at >= 60; mid band silent", () => {
    expect(componentRisks({ F: 44.9, T: 45, V: 50, S: 50, R: 50 })).toEqual([
      "Cơ bản 44,9.",
    ]);
    expect(componentRisks({ F: 45, T: 50, V: 50, S: 50, R: 50 })).toEqual([]);
    expect(componentRisks({ F: 50, T: 50, V: 50, S: 50, R: 60 })).toEqual([
      "Rủi ro cao (60,0).",
    ]);
    expect(componentRisks({ F: 50, T: 50, V: 50, S: 50, R: 59.9 })).toEqual([]);
  });

  it("R < 45 is opportunity not risk", () => {
    expect(componentOpportunities({ F: 50, T: 50, V: 50, S: 50, R: 44.9 })).toEqual([
      "Rủi ro thấp (44,9).",
    ]);
    expect(componentRisks({ F: 50, T: 50, V: 50, S: 50, R: 44.9 })).toEqual([]);
  });
});

describe("buildRiskOpportunity rules", () => {
  it("empty sides → neutral once each", () => {
    const r = buildRiskOpportunity(
      detail({ scores: { F: 50, T: 50, V: 50, S: 50, R: 50 } }),
    );
    expect(r.opportunities).toEqual([RISK_OPP_NEUTRAL]);
    expect(r.risks).toEqual([RISK_OPP_NEUTRAL]);
  });

  it("valuation cheap >15% opportunity; expensive >25% risk; mid silent", () => {
    const cheap = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m4: { pe: 8, sector_median_pe: 10 }, // -20%
      }),
    );
    expect(cheap.opportunities.some((t) => t.includes("thấp hơn"))).toBe(true);

    const near = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m4: { pe: 9, sector_median_pe: 10 }, // -10%
      }),
    );
    expect(near.opportunities).toEqual([RISK_OPP_NEUTRAL]);
    expect(near.risks).toEqual([RISK_OPP_NEUTRAL]);

    const rich = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m4: { pe: 13, sector_median_pe: 10 }, // +30%
      }),
    );
    expect(rich.risks.some((t) => t.includes("cao hơn"))).toBe(true);

    const mildRich = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m4: { pe: 12, sector_median_pe: 10 }, // +20% — not >25
      }),
    );
    expect(mildRich.risks).toEqual([RISK_OPP_NEUTRAL]);
  });

  it("max DD > 35% and ann vol > 40% are risks; boundaries", () => {
    const atDd = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m6: { max_drawdown: -0.35 },
      }),
    );
    expect(atDd.risks).toEqual([RISK_OPP_NEUTRAL]);

    const overDd = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m6: { max_drawdown: -0.351 },
      }),
    );
    expect(overDd.risks.some((t) => t.includes("sụt giảm"))).toBe(true);

    const atVol = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m6: { ann_vol: 0.4 },
      }),
    );
    expect(atVol.risks).toEqual([RISK_OPP_NEUTRAL]);

    const overVol = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m6: { ann_vol: 0.41 },
      }),
    );
    expect(overVol.risks.some((t) => t.includes("Biến động"))).toBe(true);
  });

  it("Q growth >10% opportunity; decline is risk; flat silent", () => {
    const grow = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m2: { revenue_yoy: 0.101 },
      }),
    );
    expect(grow.opportunities.some((t) => t.includes("Doanh thu"))).toBe(true);

    const at10 = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m2: { revenue_yoy: 0.1 },
      }),
    );
    expect(at10.opportunities).toEqual([RISK_OPP_NEUTRAL]);

    const down = buildRiskOpportunity(
      detail({
        scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
        m2: { net_income_yoy: -0.05 },
      }),
    );
    expect(down.risks.some((t) => t.includes("LNST"))).toBe(true);
  });

  it("does not pick strongest/weakest pillar wording", () => {
    const r = buildRiskOpportunity(
      detail({
        scores: { F: 90, T: 20, V: 50, S: 50, R: 50 },
      }),
    );
    const all = [...r.opportunities, ...r.risks].join(" ");
    expect(all.toLowerCase()).not.toContain("mạnh nhất");
    expect(all.toLowerCase()).not.toContain("yếu nhất");
    expect(all.toLowerCase()).not.toContain("trụ");
  });
});

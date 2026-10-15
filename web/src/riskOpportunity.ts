/**
 * Cơ hội / rủi ro deterministic — không theo trụ mạnh/yếu nhất; không LLM.
 *
 * Cơ hội: thành phần ≥ 60 (F/T/V/S), R < 45, định giá thấp hơn ngành > 15%,
 * tăng trưởng quý > 10%.
 * Rủi ro: F/T/V/S < 45, R ≥ 60, DD > 35%, vol năm > 40%, quý giảm,
 * định giá cao hơn ngành > 25%.
 * Khoảng 45–60: không nhắc. Bên trống → một câu trung tính.
 */

import type { RankingScores, TickerDetailResponse } from "./api/types";
import { num, pct, score } from "./fmt";
import { PILLAR_NAMES } from "./conclusion";

export const RISK_OPP_NEUTRAL = "Chưa có điểm nổi bật.";

const POSITIVE_PILLARS = ["F", "T", "V", "S"] as const;

function metricNum(
  metrics: Record<string, unknown> | undefined,
  key: string,
): number | null {
  const raw = metrics?.[key];
  if (typeof raw === "number") return raw;
  if (raw && typeof raw === "object" && "value" in raw) {
    const v = (raw as { value?: unknown }).value;
    return typeof v === "number" ? v : null;
  }
  return null;
}

/** Đưa về điểm phần trăm: 0.4 → 40; 40 → 40. */
export function asPctPoints(v: number): number {
  return Math.abs(v) <= 1.5 ? v * 100 : v;
}

function fmtGrowth(v: number): string {
  const ratio = Math.abs(v) <= 1.5 ? v : v / 100;
  return pct(ratio);
}

function label(k: string): string {
  return PILLAR_NAMES[k] || k;
}

/** Cơ hội từ điểm thành phần (xuất để unit test). */
export function componentOpportunities(
  scores: RankingScores | undefined | null,
): string[] {
  if (!scores) return [];
  const out: string[] = [];
  for (const k of POSITIVE_PILLARS) {
    const v = scores[k];
    if (typeof v === "number" && v >= 60) {
      out.push(`${label(k)} ${score(v)}.`);
    }
  }
  // R thấp = ít rủi ro → cơ hội (ngưỡng đối xứng với ≥ 60 phía rủi ro)
  const r = scores.R;
  if (typeof r === "number" && r < 45) {
    out.push(`${label("R")} thấp (${score(r)}).`);
  }
  return out;
}

/** Rủi ro từ điểm thành phần (xuất để unit test). */
export function componentRisks(
  scores: RankingScores | undefined | null,
): string[] {
  if (!scores) return [];
  const out: string[] = [];
  for (const k of POSITIVE_PILLARS) {
    const v = scores[k];
    if (typeof v === "number" && v < 45) {
      out.push(`${label(k)} ${score(v)}.`);
    }
  }
  const r = scores.R;
  if (typeof r === "number" && r >= 60) {
    out.push(`${label("R")} cao (${score(r)}).`);
  }
  return out;
}

export function buildRiskOpportunity(detail: TickerDetailResponse): {
  opportunities: string[];
  risks: string[];
} {
  const opportunities: string[] = [];
  const risks: string[] = [];
  const scores = detail.result?.scores;

  opportunities.push(...componentOpportunities(scores));
  risks.push(...componentRisks(scores));

  const m4 = detail.modules?.m4?.metrics as Record<string, unknown> | undefined;
  const pe = metricNum(m4, "pe");
  const sectorPe =
    metricNum(m4, "sector_median_pe") ?? metricNum(m4, "peer_median_pe");
  if (pe != null && sectorPe != null && sectorPe > 0) {
    const diff = ((pe - sectorPe) / sectorPe) * 100;
    if (diff < -15) {
      opportunities.push(
        `Định giá P/E ${num(pe, 1)} thấp hơn trung vị ngành ${num(sectorPe, 1)} khoảng ${num(Math.abs(diff), 0)}%.`,
      );
    }
    if (diff > 25) {
      risks.push(
        `Định giá P/E ${num(pe, 1)} cao hơn trung vị ngành ${num(sectorPe, 1)} khoảng ${num(diff, 0)}%.`,
      );
    }
  }

  const m6 = detail.modules?.m6?.metrics as Record<string, unknown> | undefined;
  const volRaw =
    metricNum(m6, "ann_vol") ??
    metricNum(m6, "volatility") ??
    metricNum(m6, "vol_60d");
  const ddRaw = metricNum(m6, "max_drawdown") ?? metricNum(m6, "drawdown");

  if (volRaw != null && asPctPoints(volRaw) > 40) {
    risks.push(`Biến động năm khoảng ${num(asPctPoints(volRaw), 1)}%.`);
  }
  if (ddRaw != null && Math.abs(asPctPoints(ddRaw)) > 35) {
    risks.push(
      `Mức sụt giảm tối đa khoảng ${num(Math.abs(asPctPoints(ddRaw)), 1)}%.`,
    );
  }

  const m2 = detail.modules?.m2?.metrics as Record<string, unknown> | undefined;
  const revG =
    metricNum(m2, "revenue_yoy") ??
    metricNum(m2, "rev_yoy") ??
    metricNum(m2, "latest_q_revenue_yoy");
  const niG =
    metricNum(m2, "ni_yoy") ??
    metricNum(m2, "net_income_yoy") ??
    metricNum(m2, "latest_q_ni_yoy");

  if (revG != null) {
    const g = asPctPoints(revG);
    if (g > 10) {
      opportunities.push(
        `Doanh thu quý gần nhất tăng ${fmtGrowth(revG)} so với cùng kỳ.`,
      );
    } else if (g < 0) {
      risks.push(
        `Doanh thu quý gần nhất giảm ${fmtGrowth(Math.abs(revG))} so với cùng kỳ.`,
      );
    }
  }
  if (niG != null) {
    const g = asPctPoints(niG);
    if (g > 10) {
      opportunities.push(
        `LNST quý gần nhất tăng ${fmtGrowth(niG)} so với cùng kỳ.`,
      );
    } else if (g < 0) {
      risks.push(
        `LNST quý gần nhất giảm ${fmtGrowth(Math.abs(niG))} so với cùng kỳ.`,
      );
    }
  }

  return {
    opportunities: opportunities.length ? opportunities : [RISK_OPP_NEUTRAL],
    risks: risks.length ? risks : [RISK_OPP_NEUTRAL],
  };
}

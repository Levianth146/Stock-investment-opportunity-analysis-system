/** Câu kết luận deterministic cho header mã. */

import type { RankingScores } from "./api/types";
import { score } from "./fmt";

const PILLAR_KEYS: (keyof RankingScores)[] = ["F", "T", "V", "S"];

/** Tên trụ hiển thị (không dùng «Đà …»). */
export const PILLAR_NAMES: Record<string, string> = {
  F: "Cơ bản",
  T: "Kỹ thuật",
  V: "Định giá",
  S: "Tin tức",
  R: "Rủi ro",
};

const STRONG: Record<string, string> = {
  F: "Điểm cơ bản cao",
  T: "Điểm kỹ thuật cao",
  V: "Định giá thấp hơn ngành",
  S: "Tin tức hỗ trợ",
};

const WEAK: Record<string, string> = {
  F: "Điểm cơ bản thấp",
  T: "Điểm kỹ thuật thấp",
  V: "Định giá cao hơn ngành",
  S: "Tin tức kém hỗ trợ",
};

function riskClause(r: number | null | undefined): string | null {
  if (r == null || Number.isNaN(r)) return null;
  if (r >= 70) return "rủi ro cao";
  if (r >= 45) return "rủi ro vừa phải";
  return "rủi ro thấp";
}

/** Mệnh đề ngắn từ trụ mạnh/yếu nhất và rủi ro. */
export function componentClause(scores: RankingScores | null | undefined): string {
  if (!scores) return "";
  let bestKey: keyof RankingScores | null = null;
  let bestVal = -Infinity;
  let worstKey: keyof RankingScores | null = null;
  let worstVal = Infinity;
  let anyPillar = false;
  for (const k of PILLAR_KEYS) {
    const v = scores[k];
    if (typeof v !== "number") continue;
    anyPillar = true;
    if (v > bestVal) {
      bestVal = v;
      bestKey = k;
    }
    if (v < worstVal) {
      worstVal = v;
      worstKey = k;
    }
  }

  const parts: string[] = [];
  if (anyPillar) {
    if (bestKey != null && bestVal >= 55) {
      parts.push(STRONG[bestKey] || "");
    } else if (worstKey != null && worstVal < 45) {
      parts.push(WEAK[worstKey] || "");
    } else if (bestKey != null) {
      parts.push(STRONG[bestKey] || "");
    }
  }

  const risk = riskClause(scores.R);
  if (risk) parts.push(risk);

  const cleaned = parts.filter(Boolean);
  if (!cleaned.length) return "";
  // Ghép: "Điểm kỹ thuật cao, rủi ro vừa phải."
  const text = cleaned.join(", ");
  return text.charAt(0).toUpperCase() + text.slice(1) + ".";
}

export function buildConclusion(opts: {
  rating: string | null | undefined;
  score: number | null | undefined;
  rank: number | null;
  n: number;
  scores?: RankingScores | null;
  unrankedReason?: string | null;
  unranked?: boolean;
}): string {
  if (opts.unranked) {
    const why =
      (opts.unrankedReason || "").trim() || "Thiếu dữ liệu để chấm điểm";
    return `Không xếp hạng. ${why}`;
  }
  const rating = opts.rating || "—";
  const sc = score(opts.score ?? null);
  const rankPart =
    opts.rank != null && opts.n > 0
      ? `đứng thứ ${opts.rank} trong ${opts.n} mã`
      : opts.n > 0
        ? `trong ${opts.n} mã có điểm`
        : "chưa có hạng";
  const head = `${rating}. Điểm ${sc}, ${rankPart}.`;
  const clause = componentClause(opts.scores);
  return clause ? `${head} ${clause}` : head;
}

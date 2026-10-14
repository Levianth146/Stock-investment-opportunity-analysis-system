/** Hạng trong tập mã đã chấm điểm — mẫu số là số mã scored, không phải page limit. */

import type { RankingRow } from "./api/types";

/**
 * Xếp hạng trong các mã đã có điểm (ranked + score số).
 * `totalScored` lấy từ /api/meta.scored_count hoặc rankings.total_scored —
 * không dùng `items.length` khi đó là trang phân trang.
 */
export function rankAmongScored(
  items: RankingRow[] | null | undefined,
  symbol: string,
  totalScored?: number | null,
): { rank: number | null; n: number } {
  const scored = (items || []).filter(
    (r) => r.ranked && typeof r.score === "number",
  );
  const sym = symbol.toUpperCase();
  const idx = scored.findIndex((r) => r.ticker.toUpperCase() === sym);
  const fromMeta =
    typeof totalScored === "number" && totalScored > 0 ? totalScored : null;
  const n = fromMeta ?? scored.length;
  return {
    rank: idx >= 0 ? idx + 1 : null,
    n,
  };
}

/** Tìm mã/tên không dấu từ payload rankings đã cache. */

import type { RankingRow } from "./api/types";

/** Bỏ dấu tiếng Việt để khớp tìm kiếm. */
export function stripDiacritics(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D");
}

export interface SearchHit {
  ticker: string;
  name: string | null;
  sector: string | null;
  score: number | null;
}

/** Lọc tối đa ``limit`` kết quả theo prefix mã hoặc tên (không dấu). */
export function searchRankings(
  items: RankingRow[],
  query: string,
  limit = 8,
): SearchHit[] {
  const q = stripDiacritics(query.trim()).toUpperCase();
  if (!q) return [];
  const hits: SearchHit[] = [];
  for (const row of items) {
    const sym = (row.ticker || "").toUpperCase();
    const name = stripDiacritics(row.name || "").toUpperCase();
    if (sym.startsWith(q) || name.includes(q)) {
      hits.push({
        ticker: row.ticker,
        name: row.name,
        sector: row.sector,
        score: row.score,
      });
      if (hits.length >= limit) break;
    }
  }
  return hits;
}

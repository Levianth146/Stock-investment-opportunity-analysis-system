import { describe, expect, it } from "vitest";
import type { RankingRow } from "./api/types";
import { rankAmongScored } from "./rank";
import { buildConclusion } from "./conclusion";

function row(
  ticker: string,
  score: number | null,
  ranked = true,
): RankingRow {
  return {
    ticker,
    name: ticker,
    sector: "Steel",
    score,
    rating: ranked && score != null ? "Mua" : "Không xếp hạng",
    scores: { F: score, T: score, V: score, S: score, R: 40 },
    ranked,
  };
}

describe("rankAmongScored", () => {
  it("uses scored_count (235) not page items length; ignores unranked", () => {
    const scored: RankingRow[] = [];
    for (let i = 0; i < 50; i++) {
      scored.push(row(`T${String(i).padStart(3, "0")}`, 90 - i * 0.1));
    }
    // PVT đứng thứ 12 trong 50 trang đầu, nhưng tổng scored = 235
    scored[11] = row("PVT", 80);
    const unranked = [row("ZZZ", null, false), row("YYY", null, false)];
    const page = [...scored, ...unranked];

    const info = rankAmongScored(page, "PVT", 235);
    expect(info.n).toBe(235);
    expect(info.rank).toBe(12);
    expect(info.n).not.toBe(page.length);
    expect(info.n).not.toBe(50);

    const sentence = buildConclusion({
      rating: "Mua",
      score: 80,
      rank: info.rank,
      n: info.n,
      scores: { F: 70, T: 60, V: 80, S: 55, R: 40 },
    });
    expect(sentence).toContain("đứng thứ 12 trong 235 mã");
  });

  it("falls back to scored items length when totalScored missing", () => {
    const items = [
      row("AAA", 90),
      row("BBB", 80),
      row("CCC", null, false),
      row("DDD", 70),
    ];
    const info = rankAmongScored(items, "DDD", null);
    expect(info.n).toBe(3);
    expect(info.rank).toBe(3);
  });

  it("rank null when symbol not in scored set", () => {
    const items = [row("AAA", 90), row("BBB", null, false)];
    expect(rankAmongScored(items, "ZZZ", 100)).toEqual({
      rank: null,
      n: 100,
    });
  });
});

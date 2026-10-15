import { describe, expect, it } from "vitest";
import type { RankingRow } from "./api/types";
import { searchRankings, stripDiacritics } from "./search";

const rows: RankingRow[] = [
  {
    ticker: "VNM",
    name: "Vinamilk",
    sector: "Food",
    score: 70,
    rating: "Mua",
    scores: { F: 1, T: 1, V: 1, S: 1, R: 1 },
    ranked: true,
  },
  {
    ticker: "HPG",
    name: "Hòa Phát",
    sector: "Steel",
    score: 65,
    rating: "Mua",
    scores: { F: 1, T: 1, V: 1, S: 1, R: 1 },
    ranked: true,
  },
  {
    ticker: "VCB",
    name: "Vietcombank",
    sector: "Banks",
    score: 80,
    rating: "Mua mạnh",
    scores: { F: 1, T: 1, V: 1, S: 1, R: 1 },
    ranked: true,
  },
];

describe("stripDiacritics", () => {
  it("removes Vietnamese marks", () => {
    expect(stripDiacritics("Hòa Phát")).toBe("Hoa Phat");
    expect(stripDiacritics("Đà Nẵng")).toBe("Da Nang");
  });
});

describe("searchRankings", () => {
  it("matches symbol prefix", () => {
    expect(searchRankings(rows, "vn").map((x) => x.ticker)).toEqual(["VNM"]);
    expect(searchRankings(rows, "vc").map((x) => x.ticker)).toEqual(["VCB"]);
  });

  it("matches name without diacritics", () => {
    const h = searchRankings(rows, "hoa phat");
    expect(h).toHaveLength(1);
    expect(h[0]!.ticker).toBe("HPG");
  });

  it("caps at 8", () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...rows[0]!,
      ticker: `V${String(i).padStart(2, "0")}`,
      name: `Vinamilk ${i}`,
    }));
    expect(searchRankings(many, "v", 8)).toHaveLength(8);
  });

  it("empty query → empty", () => {
    expect(searchRankings(rows, "  ")).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";
import { buildConclusion, componentClause } from "./conclusion";

describe("buildConclusion", () => {
  it("unranked shows reason", () => {
    const s = buildConclusion({
      rating: "Không xếp hạng",
      score: null,
      rank: null,
      n: 10,
      unranked: true,
      unrankedReason: "Thiếu BCTC",
    });
    expect(s).toContain("Không xếp hạng");
    expect(s).toContain("Thiếu BCTC");
  });

  it("ranked sentence with rank", () => {
    const s = buildConclusion({
      rating: "Mua",
      score: 68.4,
      rank: 12,
      n: 95,
      scores: { F: 70, T: 40, V: 80, S: 55, R: 50 },
    });
    expect(s).toMatch(/^Mua\./);
    expect(s).toContain("Điểm 68,4");
    expect(s).toContain("đứng thứ 12 trong 95 mã");
    expect(s.toLowerCase()).toContain("định giá");
  });

  it.each([
    ["Mua mạnh", 82],
    ["Mua", 65],
    ["Nắm giữ", 50],
    ["Giảm tỷ trọng", 35],
    ["Bán", 20],
  ] as const)("rating %s appears as head", (rating, sc) => {
    const s = buildConclusion({
      rating,
      score: sc,
      rank: 1,
      n: 10,
      scores: { F: 50, T: 50, V: 50, S: 50, R: 50 },
    });
    expect(s.startsWith(`${rating}.`)).toBe(true);
    expect(s.toLowerCase()).not.toContain("đà");
  });

  it("works when all pillars missing — only risk", () => {
    const s = buildConclusion({
      rating: "Nắm giữ",
      score: 50,
      rank: 5,
      n: 20,
      scores: { F: null, T: null, V: null, S: null, R: 40 },
    });
    expect(s).toContain("Nắm giữ");
    expect(s.toLowerCase()).toContain("rủi ro thấp");
    expect(s.toLowerCase()).not.toContain("đà");
  });

  it("works when scores object missing", () => {
    const s = buildConclusion({
      rating: "Mua",
      score: 62,
      rank: 3,
      n: 10,
      scores: null,
    });
    expect(s).toMatch(/^Mua\./);
    expect(s).not.toMatch(/rủi ro/);
  });
});

describe("componentClause", () => {
  it("picks strong T and mid risk — no Đà", () => {
    const c = componentClause({ F: 50, T: 85, V: 50, S: 50, R: 50 });
    expect(c).toBe("Điểm kỹ thuật cao, rủi ro vừa phải.");
    expect(c.toLowerCase()).not.toContain("đà");
  });

  it("picks strong V", () => {
    const c = componentClause({ F: 50, T: 50, V: 85, S: 50, R: 50 });
    expect(c.toLowerCase()).toContain("định giá thấp hơn ngành");
    expect(c.toLowerCase()).toContain("rủi ro vừa phải");
  });

  it("weak F and high risk", () => {
    const c = componentClause({ F: 20, T: 50, V: 50, S: 50, R: 80 });
    expect(c.toLowerCase()).toContain("điểm cơ bản thấp");
    expect(c.toLowerCase()).toContain("rủi ro cao");
  });

  it("missing pillars returns empty or risk-only", () => {
    expect(componentClause(null)).toBe("");
    expect(componentClause(undefined)).toBe("");
    expect(componentClause({ F: null, T: null, V: null, S: null, R: null })).toBe(
      "",
    );
    expect(componentClause({ F: null, T: null, V: null, S: null, R: 30 })).toBe(
      "Rủi ro thấp.",
    );
  });

  it("uses Tin tức not Tin", () => {
    const c = componentClause({ F: 40, T: 40, V: 40, S: 90, R: 20 });
    expect(c.toLowerCase()).toContain("tin tức");
    expect(c.toLowerCase()).not.toContain("đà");
  });
});

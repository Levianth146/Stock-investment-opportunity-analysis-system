import { describe, expect, it } from "vitest";
import { breadthCoversUniverse, breadthSum, normalizeBreadth } from "./breadth";

describe("breadth", () => {
  it("4 nhóm cộng đúng tổng", () => {
    const b = normalizeBreadth({ up: 80, down: 60, flat: 40, unmatched: 55 });
    expect(breadthSum(b)).toBe(235);
    expect(breadthCoversUniverse(b, 235)).toBe(true);
  });

  it("thiếu khóa → 0", () => {
    expect(breadthSum(normalizeBreadth({ up: 1 }))).toBe(1);
  });
});

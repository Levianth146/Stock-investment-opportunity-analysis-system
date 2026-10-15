import { describe, expect, it } from "vitest";
import { areaSum, squarify } from "./squarify";

describe("squarify", () => {
  it("tổng diện tích ≈ width×height", () => {
    const items = [
      { id: "a", weight: 40 },
      { id: "b", weight: 30 },
      { id: "c", weight: 20 },
      { id: "d", weight: 10 },
    ];
    const W = 200;
    const H = 100;
    const rects = squarify(items, W, H);
    expect(rects.length).toBe(4);
    const sum = areaSum(rects);
    expect(sum).toBeGreaterThan(W * H * 0.98);
    expect(sum).toBeLessThanOrEqual(W * H * 1.02);
  });

  it("bỏ weight ≤ 0", () => {
    const rects = squarify(
      [
        { id: "a", weight: 10 },
        { id: "b", weight: 0 },
        { id: "c", weight: -1 },
      ],
      100,
      100,
    );
    expect(rects.map((r) => r.id)).toEqual(["a"]);
  });
});

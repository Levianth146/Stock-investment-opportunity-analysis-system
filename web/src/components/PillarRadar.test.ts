import { describe, expect, it } from "vitest";
import { radarPoints } from "./PillarRadar";

describe("radarPoints geometry", () => {
  it("returns 5 coordinate pairs for pentagon", () => {
    const pts = radarPoints([100, 100, 100, 100, 100], 110, 110, 72);
    const pairs = pts.split(" ");
    expect(pairs).toHaveLength(5);
    // đỉnh trên cùng (i=0) tại góc -90° → x=cx, y=cy-r
    const [x0, y0] = pairs[0]!.split(",").map(Number);
    expect(x0).toBeCloseTo(110, 5);
    expect(y0).toBeCloseTo(110 - 72, 5);
  });

  it("zero radius collapses to center", () => {
    const pts = radarPoints([0, 0, 0, 0, 0], 50, 50, 40);
    for (const p of pts.split(" ")) {
      const [x, y] = p.split(",").map(Number);
      expect(x).toBeCloseTo(50, 5);
      expect(y).toBeCloseTo(50, 5);
    }
  });
});

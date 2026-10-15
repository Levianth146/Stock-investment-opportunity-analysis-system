import { describe, expect, it } from "vitest";
import { changeToColor, formatChangeLabel } from "./colorScale";

describe("colorScale", () => {
  it("định dạng nhãn %", () => {
    expect(formatChangeLabel(1.23)).toBe("+1.2");
    expect(formatChangeLabel(-2.56)).toBe("-2.6");
    expect(formatChangeLabel(null)).toBe("");
  });

  it("màu phân kỳ khác nhau cho âm / dương / null", () => {
    const up = changeToColor(4);
    const down = changeToColor(-4);
    const mid = changeToColor(0);
    const miss = changeToColor(null);
    expect(up).not.toBe(down);
    expect(up).not.toBe(mid);
    expect(miss).toMatch(/rgb|#/);
  });
});

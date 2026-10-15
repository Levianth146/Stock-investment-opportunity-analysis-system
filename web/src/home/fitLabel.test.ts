import { describe, expect, it } from "vitest";
import { fitLabel } from "./SectorHeatmap";

describe("fitLabel", () => {
  it("giữ nguyên khi đủ chỗ", () => {
    expect(fitLabel("Ngân hàng", 200)).toBe("Ngân hàng");
  });
  it("cắt và thêm … khi hẹp", () => {
    const out = fitLabel("Bất động sản", 45);
    expect(out.endsWith("…")).toBe(true);
    expect(out.length).toBeLessThan("Bất động sản".length);
  });
  it("ẩn nhãn khi ô quá nhỏ", () => {
    expect(fitLabel("Ngân hàng", 10)).toBe("");
  });
});

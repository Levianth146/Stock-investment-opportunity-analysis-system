import { describe, expect, it } from "vitest";
import { evaluateRefPrice, REF_UNRELIABLE_TIP } from "./refPrice";

describe("evaluateRefPrice", () => {
  it("hiển thị khi lệch nhỏ", () => {
    const v = evaluateRefPrice(100, 110);
    expect(v.display).toBe(110);
    expect(v.unreliable).toBe(false);
    expect(v.deviation).toBeCloseTo(0.1);
  });

  it("ẩn khi lệch > 50%", () => {
    const v = evaluateRefPrice(100, 160);
    expect(v.display).toBeNull();
    expect(v.unreliable).toBe(true);
    expect(v.tooltip).toBe(REF_UNRELIABLE_TIP);
    expect(v.deviation).toBeNull();
  });

  it("thiếu dữ liệu → null", () => {
    expect(evaluateRefPrice(null, 100).display).toBeNull();
    expect(evaluateRefPrice(100, null).display).toBeNull();
  });
});

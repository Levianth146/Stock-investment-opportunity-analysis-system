import { describe, expect, it } from "vitest";
import { bestIndex, parseSymbols } from "./ComparePage";

describe("parseSymbols", () => {
  it("chuẩn hóa, bỏ trùng và giới hạn 4 mã", () => {
    expect(parseSymbols("aaa, BBB,aaa,ccc,ddd,eee")).toEqual(["AAA", "BBB", "CCC", "DDD"]);
  });
  it("bỏ giá trị không hợp lệ", () => {
    expect(parseSymbols("a,<x>,VNM")).toEqual(["VNM"]);
    expect(parseSymbols(null)).toEqual([]);
  });
});

describe("bestIndex", () => {
  it("cao hơn là tốt hơn, R thấp hơn là tốt hơn", () => {
    expect(bestIndex([40, 70, 55])).toBe(1);
    expect(bestIndex([40, 70, 55], true)).toBe(0);
  });
  it("bỏ qua null và không tô khi chỉ có một giá trị", () => {
    expect(bestIndex([null, 60, undefined])).toBe(-1);
    expect(bestIndex([null, 60, 80])).toBe(2);
  });
});

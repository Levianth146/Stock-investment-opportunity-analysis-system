import { describe, expect, it } from "vitest";
import { changePctLabel, dateVi, num, pct, score } from "./fmt";

describe("fmt", () => {
  it("định dạng số kiểu Việt", () => {
    expect(num(1234.5)).toMatch(/1\.234/);
    expect(num(null)).toBe("—");
  });

  it("phần trăm", () => {
    expect(pct(0.123, { digits: 1 })).toContain("%");
    expect(pct(12.3, { alreadyPercent: true, digits: 1 })).toContain("%");
  });

  it("điểm và ngày", () => {
    expect(score(58.6)).toBe("58,6");
    expect(dateVi("2026-10-08")).toBe("08/10/2026");
  });

  it("changePctLabel — khi chưa có giá tham chiếu", () => {
    const r = changePctLabel(null, { prevCloseSource: "none" });
    expect(r.text).toBe("—");
    expect(r.note).toBe("chưa có giá tham chiếu");
    const ok = changePctLabel(1.5, { prevCloseSource: "snapshot" });
    expect(ok.text).toContain("%");
    expect(ok.note).toBeNull();
  });
});

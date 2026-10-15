import { describe, expect, it } from "vitest";
import { sectorVi } from "./sectors";

describe("sectorVi", () => {
  it("map ICB L2 quen thuộc", () => {
    expect(sectorVi("Banks")).toBe("Ngân hàng");
    expect(sectorVi("Industrial Goods & Services")).toBe(
      "Hàng & dịch vụ công nghiệp",
    );
  });

  it("không biết → giữ nguyên", () => {
    expect(sectorVi("Weird Sector XYZ")).toBe("Weird Sector XYZ");
  });

  it("null/rỗng", () => {
    expect(sectorVi(null)).toBe("—");
    expect(sectorVi("")).toBe("—");
  });
});

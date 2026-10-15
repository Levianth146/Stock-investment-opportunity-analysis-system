import { describe, expect, it } from "vitest";
import { FIN_UNIT_ROE_NOTE } from "./finNotes";

describe("finNotes", () => {
  it("chú thích ROE tiếng Việt, không chuỗi mã API", () => {
    expect(FIN_UNIT_ROE_NOTE).toContain("tỷ đồng");
    expect(FIN_UNIT_ROE_NOTE).toContain("ROE năm");
    expect(FIN_UNIT_ROE_NOTE).toContain("ROE quý chưa quy năm");
    expect(FIN_UNIT_ROE_NOTE).not.toMatch(/avg_equity|ending_equity|annualize/i);
  });
});

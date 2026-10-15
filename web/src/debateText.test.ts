import { describe, expect, it } from "vitest";
import {
  cleanDebateItems,
  dedupeDebateByMetrics,
  stripDebatePadding,
} from "./debateText";

describe("stripDebatePadding", () => {
  it("strips Thêm dẫn chứng prefix", () => {
    expect(
      stripDebatePadding("Thêm dẫn chứng Cơ bản: ROE 18,2%."),
    ).toBe("ROE 18,2%.");
  });

  it("leaves normal debate text", () => {
    expect(stripDebatePadding("Biên lợi nhuận cải thiện.")).toBe(
      "Biên lợi nhuận cải thiện.",
    );
  });

  it("filters empty after strip in cleanDebateItems", () => {
    const out = cleanDebateItems([
      { text: "Thuận chính.", refs: ["a"] },
      { text: "Thêm dẫn chứng Định giá: P/E 8.", refs: ["b"] },
      { text: "Thêm dẫn chứng tin tức." },
    ]);
    expect(out.map((x) => x.text)).toEqual([
      "Thuận chính.",
      "P/E 8.",
    ]);
  });

  it("dedupes bullets that repeat metrics already stated", () => {
    const out = dedupeDebateByMetrics([
      { text: "ROE 18,2% cao hơn ngành.", refs: ["m2.roe"] },
      { text: "ROE tiếp tục cải thiện năm nay.", refs: ["m2.roe"] },
      { text: "P/E 8 thấp hơn trung vị.", refs: ["m4.pe"] },
    ]);
    expect(out.map((x) => x.text)).toEqual([
      "ROE 18,2% cao hơn ngành.",
      "P/E 8 thấp hơn trung vị.",
    ]);
  });
});

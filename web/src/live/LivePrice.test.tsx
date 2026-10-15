import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LiveChangePct } from "./LivePrice";
import { bannerForState, canShowSessionMetrics, reasonVi } from "./staleness";

describe("LiveChangePct — không hiện +0% giả", () => {
  it("null / NaN → em dash", () => {
    const html = renderToStaticMarkup(<LiveChangePct value={null} />);
    expect(html).toContain("—");
    expect(html).not.toContain("+0");
    expect(html).not.toContain("0%");
  });

  it("snapshot: thiếu số → chỉ —", () => {
    const html = renderToStaticMarkup(<LiveChangePct value={undefined} />);
    expect(html).toMatchSnapshot();
  });

  it("có số hợp lệ thì hiện ±%", () => {
    const up = renderToStaticMarkup(<LiveChangePct value={1.5} />);
    expect(up).toContain("+");
    expect(up).toContain("%");
    expect(up).not.toContain("—");
  });
});

describe("banner / reason no_realtime", () => {
  it("reasonVi ngắn, không lộ secrets", () => {
    expect(reasonVi("missing_key")).toMatch(/khóa/i);
    expect(reasonVi("disabled")).toMatch(/tắt/i);
    expect(reasonVi("sdk_missing")).toMatch(/thư viện/i);
    expect(reasonVi("connect_error:TimeoutError")).toMatch(/kết nối/i);
    expect(reasonVi("connect_error:TimeoutError")).not.toMatch(/TimeoutError/);
  });

  it("banner dùng reason cụ thể khi no_realtime", () => {
    const b = bannerForState("no_realtime", null, "missing_key");
    expect(b).toMatch(/khóa/i);
    expect(b).toMatch(/EOD/);
  });

  it("canShowSessionMetrics", () => {
    expect(canShowSessionMetrics({ state: "live" })).toBe(true);
    expect(canShowSessionMetrics({ state: "closed" })).toBe(true);
    expect(canShowSessionMetrics({ sessionPhase: "closed" })).toBe(true);
    expect(
      canShowSessionMetrics({ state: "no_realtime", sessionPhase: "continuous" }),
    ).toBe(false);
  });
});

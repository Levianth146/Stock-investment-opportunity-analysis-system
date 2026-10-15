import { describe, expect, it } from "vitest";
import {
  DISPLAY_STALE_MS,
  bannerForState,
  canShowSessionMetrics,
  resolveDisplayState,
} from "./staleness";

describe("staleness by receive time", () => {
  it("live khi vừa nhận", () => {
    const now = 10_000;
    expect(
      resolveDisplayState(
        { state: "live", receivedAt: now - 5_000 },
        { now, sessionOpen: true },
      ),
    ).toBe("live");
  });

  it("stale khi >20s không tick (theo receive)", () => {
    const now = 50_000;
    expect(
      resolveDisplayState(
        { state: "live", receivedAt: now - DISPLAY_STALE_MS - 1 },
        { now, sessionOpen: true },
      ),
    ).toBe("stale");
  });

  it("không so sánh với tick.ts / đồng hồ tường", () => {
    // receivedAt gần đây dù "ts" tick cũ — vẫn live
    const now = 100_000;
    expect(
      resolveDisplayState(
        { state: "live", receivedAt: now - 1_000 },
        { now, sessionOpen: true },
      ),
    ).toBe("live");
  });

  it("giữ closed / unit_mismatch", () => {
    expect(resolveDisplayState({ state: "closed" }, { sessionOpen: false })).toBe(
      "closed",
    );
    expect(
      resolveDisplayState({ state: "unit_mismatch", receivedAt: 0 }, { now: 99999 }),
    ).toBe("unit_mismatch");
  });
});

describe("session metrics gate", () => {
  it("no_realtime trong phiên → không hiện %", () => {
    expect(
      canShowSessionMetrics({ state: "no_realtime", sessionPhase: "continuous" }),
    ).toBe(false);
    expect(bannerForState("no_realtime", null, "missing_key")).toMatch(/khóa/);
  });

  it("connecting / no_ticks_yet — không tuyên bố trực tiếp", () => {
    expect(
      canShowSessionMetrics({ state: "connecting", sessionPhase: "continuous" }),
    ).toBe(false);
    const b = bannerForState("connecting", null, "no_ticks_yet");
    expect(b).toMatch(/tick/i);
    expect(b).not.toMatch(/trực tiếp \(tạm tính\)/);
  });

  it("stale no_ticks — banner tiếng Việt", () => {
    const b = bannerForState("stale", null, "no_ticks");
    expect(b).toMatch(/90|tick|EOD/i);
  });
});

import { describe, expect, it } from "vitest";
import type { RealtimeMarketResponse } from "../api/types";
import { applyMessage } from "./marketStream";

const base = (): RealtimeMarketResponse =>
  ({
    asof: "2026-10-14",
    index: {
      price: { value: 1200 },
      candles_1m: [{ t: 1, c: 1199 }],
      series_eod: [{ time: "2026-10-13", close: 1190 }],
    },
    breadth: { up: { value: 1 } },
    heatmap: [
      { symbol: "AAA", sector: "Banks", change_pct: { value: 0, basis: "eod" }, market_cap_ref: 100 },
      { symbol: "BBB", sector: "Steel", change_pct: { value: 1, basis: "live" }, market_cap_ref: 50 },
    ],
  }) as unknown as RealtimeMarketResponse;

describe("applyMessage", () => {
  it("full thay toàn bộ và đặt seq", () => {
    const r = applyMessage(null, 0, { type: "full", seq: 1, payload: base() });
    expect(r?.seq).toBe(1);
    expect(r?.data?.heatmap).toHaveLength(2);
  });

  it("delta heatmap chỉ đổi mã được gửi, giữ market_cap_ref", () => {
    const r = applyMessage(base(), 1, {
      type: "delta",
      seq: 2,
      heatmap: [["AAA", 2.5, "tạm tính", "live"]],
    });
    const hm = r!.data!.heatmap!;
    expect(hm[0]!.change_pct?.value).toBe(2.5);
    expect(hm[0]!.change_pct?.basis).toBe("live");
    expect(hm[0]!.market_cap_ref).toBe(100);
    expect(hm[1]!.change_pct?.value).toBe(1);
  });

  it("delta index gộp nến theo t và giữ series_eod", () => {
    const r = applyMessage(base(), 1, {
      type: "delta",
      seq: 2,
      index: { price: { value: 1201 }, candles_tail: [{ t: 1, c: 1200 }, { t: 2, c: 1201 }], candles_count: 2 },
    });
    const idx = r!.data!.index!;
    expect(idx.price?.value).toBe(1201);
    expect(idx.candles_1m).toEqual([{ t: 1, c: 1200 }, { t: 2, c: 1201 }]);
    expect(idx.series_eod).toHaveLength(1);
  });

  it("lệch seq → null (phải kết nối lại để lấy full)", () => {
    expect(applyMessage(base(), 1, { type: "delta", seq: 3 })).toBeNull();
    expect(applyMessage(base(), 5, { type: "heartbeat", seq: 4 })).toBeNull();
  });

  it("delta khi chưa có full → null", () => {
    expect(applyMessage(null, 0, { type: "delta", seq: 1 })).toBeNull();
  });

  it("heartbeat đúng seq giữ nguyên dữ liệu", () => {
    const d = base();
    const r = applyMessage(d, 7, { type: "heartbeat", seq: 7 });
    expect(r?.data).toBe(d);
  });
});

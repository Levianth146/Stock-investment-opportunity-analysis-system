import { describe, expect, it } from "vitest";
import { adx, analyze, bollinger, ema, gaugeOf, macd, rsi, sma, stochastic, verdictOf, withLive, type Bar } from "./indicators";
import { narrate } from "./narrative";

function series(n: number, f: (i: number) => number): Bar[] {
  return Array.from({ length: n }, (_, i) => {
    const c = f(i);
    const d = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10);
    return { time: d, open: c, high: c * 1.01, low: c * 0.99, close: c, volume: 1000 + i };
  });
}

describe("indicators", () => {
  it("sma/ema trên chuỗi hằng", () => {
    const v = Array(50).fill(10);
    expect(sma(v, 20)).toBe(10);
    expect(ema(v, 12)).toBeCloseTo(10);
  });
  it("RSI: tăng liên tục ≈100, giảm liên tục ≈0", () => {
    const up = Array.from({ length: 40 }, (_, i) => 10 + i);
    const dn = Array.from({ length: 40 }, (_, i) => 100 - i);
    expect(rsi(up)).toBeGreaterThan(95);
    expect(rsi(dn)).toBeLessThan(5);
  });
  it("MACD dương khi tăng đều", () => {
    const m = macd(Array.from({ length: 80 }, (_, i) => 10 + i * 0.5));
    expect(m!.macd).toBeGreaterThan(0);
  });
  it("Bollinger %B của giá cuối cao hơn nền", () => {
    const c = [...Array(19).fill(10), 14];
    expect(bollinger(c)!.pctB).toBeGreaterThan(0.9);
  });
  it("Stochastic trần khi đóng cửa tại đỉnh", () => {
    const bars = series(30, (i) => 10 + i);
    bars[bars.length - 1] = { ...bars[bars.length - 1]!, close: bars[bars.length - 1]!.high };
    expect(stochastic(bars)!.k).toBeGreaterThan(95);
  });
  it("ADX mạnh khi xu hướng tăng đều", () => {
    expect(adx(series(80, (i) => 10 + i))!.adx).toBeGreaterThan(25);
  });
  it("verdictOf theo ngưỡng", () => {
    expect(verdictOf(-0.7)).toBe("strong_sell");
    expect(verdictOf(0)).toBe("neutral");
    expect(verdictOf(0.3)).toBe("buy");
    expect(verdictOf(0.9)).toBe("strong_buy");
  });
  it("gaugeOf đếm đúng", () => {
    const g = gaugeOf([
      { id: "a", name: "a", group: "ma", value: "", signal: "buy", note: "" },
      { id: "b", name: "b", group: "ma", value: "", signal: "sell", note: "" },
      { id: "c", name: "c", group: "ma", value: "", signal: "neutral", note: "" },
    ]);
    expect([g.buy, g.sell, g.neutral, g.score]).toEqual([1, 1, 1, 0]);
  });
});

describe("withLive", () => {
  const bars = series(40, (i) => 10 + i);
  it("ghép nến mới khi chưa có nến hôm nay", () => {
    const out = withLive(bars, { price: 99, volume: 5 }, "2026-12-31");
    expect(out.length).toBe(bars.length + 1);
    expect(out[out.length - 1]!.close).toBe(99);
  });
  it("thay giá đóng nến hôm nay", () => {
    const today = bars[bars.length - 1]!.time;
    const out = withLive(bars, { price: 99 }, today);
    expect(out.length).toBe(bars.length);
    expect(out[out.length - 1]!.close).toBe(99);
  });
  it("không live → giữ nguyên", () => {
    expect(withLive(bars, null, "2026-12-31")).toBe(bars);
  });
});

describe("analyze + narrate", () => {
  it("xu hướng tăng → tổng hợp nghiêng mua và có diễn giải", () => {
    const r = analyze(series(260, (i) => 10 + i * 0.1))!;
    expect(r.ma.verdict === "buy" || r.ma.verdict === "strong_buy").toBe(true);
    const blocks = narrate(r);
    expect(blocks.map((b) => b.head)).toContain("Tổng hợp");
    expect(blocks[0]!.text).toMatch(/xu hướng tăng/);
  });
  it("quá ít dữ liệu → null", () => {
    expect(analyze(series(10, (i) => i + 1))).toBeNull();
  });
});

/** Chỉ báo kỹ thuật thuần (không phụ thuộc UI) — tính từ nến ngày + giá trực tiếp (nếu có). */

export interface Bar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type Sig = "buy" | "neutral" | "sell";

export function sma(v: number[], n: number): number | null {
  if (v.length < n) return null;
  let s = 0;
  for (let i = v.length - n; i < v.length; i++) s += v[i]!;
  return s / n;
}

export function emaSeries(v: number[], n: number): number[] {
  if (v.length < n) return [];
  const k = 2 / (n + 1);
  let e = v.slice(0, n).reduce((a, b) => a + b, 0) / n;
  const out = [e];
  for (let i = n; i < v.length; i++) {
    e = v[i]! * k + e * (1 - k);
    out.push(e);
  }
  return out;
}

export function ema(v: number[], n: number): number | null {
  const s = emaSeries(v, n);
  return s.length ? s[s.length - 1]! : null;
}

/** RSI Wilder. */
export function rsi(close: number[], n = 14): number | null {
  if (close.length <= n) return null;
  let g = 0;
  let l = 0;
  for (let i = 1; i <= n; i++) {
    const d = close[i]! - close[i - 1]!;
    if (d >= 0) g += d;
    else l -= d;
  }
  g /= n;
  l /= n;
  for (let i = n + 1; i < close.length; i++) {
    const d = close[i]! - close[i - 1]!;
    g = (g * (n - 1) + (d > 0 ? d : 0)) / n;
    l = (l * (n - 1) + (d < 0 ? -d : 0)) / n;
  }
  if (l === 0) return 100;
  return 100 - 100 / (1 + g / l);
}

export function macd(close: number[], fast = 12, slow = 26, sig = 9) {
  const ef = emaSeries(close, fast);
  const es = emaSeries(close, slow);
  if (!es.length) return null;
  const off = ef.length - es.length;
  const line = es.map((x, i) => ef[i + off]! - x);
  const sg = emaSeries(line, sig);
  if (!sg.length) return null;
  const m = line[line.length - 1]!;
  const s = sg[sg.length - 1]!;
  return { macd: m, signal: s, hist: m - s };
}

export function bollinger(close: number[], n = 20, k = 2) {
  if (close.length < n) return null;
  const w = close.slice(-n);
  const mid = w.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(w.reduce((a, b) => a + (b - mid) ** 2, 0) / n);
  const up = mid + k * sd;
  const lo = mid - k * sd;
  const last = close[close.length - 1]!;
  return {
    mid,
    up,
    lo,
    pctB: up === lo ? 0.5 : (last - lo) / (up - lo),
    widthPct: mid ? ((up - lo) / mid) * 100 : 0,
  };
}

export function stochastic(bars: Bar[], n = 14, smooth = 3) {
  if (bars.length < n + smooth - 1) return null;
  const ks: number[] = [];
  for (let i = n - 1; i < bars.length; i++) {
    const w = bars.slice(i - n + 1, i + 1);
    const hh = Math.max(...w.map((b) => b.high));
    const ll = Math.min(...w.map((b) => b.low));
    ks.push(hh === ll ? 50 : ((bars[i]!.close - ll) / (hh - ll)) * 100);
  }
  const k = ks[ks.length - 1]!;
  const d = ks.slice(-smooth).reduce((a, b) => a + b, 0) / smooth;
  return { k, d };
}

export function williamsR(bars: Bar[], n = 14): number | null {
  if (bars.length < n) return null;
  const w = bars.slice(-n);
  const hh = Math.max(...w.map((b) => b.high));
  const ll = Math.min(...w.map((b) => b.low));
  return hh === ll ? -50 : ((hh - bars[bars.length - 1]!.close) / (hh - ll)) * -100;
}

export function cci(bars: Bar[], n = 20): number | null {
  if (bars.length < n) return null;
  const tp = bars.map((b) => (b.high + b.low + b.close) / 3);
  const w = tp.slice(-n);
  const m = w.reduce((a, b) => a + b, 0) / n;
  const md = w.reduce((a, b) => a + Math.abs(b - m), 0) / n;
  return md === 0 ? 0 : (tp[tp.length - 1]! - m) / (0.015 * md);
}

export function atr(bars: Bar[], n = 14): number | null {
  if (bars.length <= n) return null;
  const tr = (i: number) =>
    Math.max(
      bars[i]!.high - bars[i]!.low,
      Math.abs(bars[i]!.high - bars[i - 1]!.close),
      Math.abs(bars[i]!.low - bars[i - 1]!.close),
    );
  let a = 0;
  for (let i = 1; i <= n; i++) a += tr(i);
  a /= n;
  for (let i = n + 1; i < bars.length; i++) a = (a * (n - 1) + tr(i)) / n;
  return a;
}

/** ADX Wilder + DI. */
export function adx(bars: Bar[], n = 14) {
  if (bars.length < 2 * n + 1) return null;
  let trS = 0;
  let pS = 0;
  let mS = 0;
  const dxs: number[] = [];
  let pdi = 0;
  let mdi = 0;
  for (let i = 1; i < bars.length; i++) {
    const up = bars[i]!.high - bars[i - 1]!.high;
    const dn = bars[i - 1]!.low - bars[i]!.low;
    const p = up > dn && up > 0 ? up : 0;
    const m = dn > up && dn > 0 ? dn : 0;
    const tr = Math.max(
      bars[i]!.high - bars[i]!.low,
      Math.abs(bars[i]!.high - bars[i - 1]!.close),
      Math.abs(bars[i]!.low - bars[i - 1]!.close),
    );
    if (i <= n) {
      trS += tr;
      pS += p;
      mS += m;
    } else {
      trS = trS - trS / n + tr;
      pS = pS - pS / n + p;
      mS = mS - mS / n + m;
    }
    if (i >= n) {
      pdi = trS ? (100 * pS) / trS : 0;
      mdi = trS ? (100 * mS) / trS : 0;
      const s = pdi + mdi;
      dxs.push(s ? (100 * Math.abs(pdi - mdi)) / s : 0);
    }
  }
  if (dxs.length < n) return null;
  let a = dxs.slice(0, n).reduce((x, y) => x + y, 0) / n;
  for (let i = n; i < dxs.length; i++) a = (a * (n - 1) + dxs[i]!) / n;
  return { adx: a, pdi, mdi };
}

export function obvTrend(bars: Bar[], n = 20): number | null {
  if (bars.length < n + 1) return null;
  let o = 0;
  const series = [0];
  for (let i = 1; i < bars.length; i++) {
    if (bars[i]!.close > bars[i - 1]!.close) o += bars[i]!.volume;
    else if (bars[i]!.close < bars[i - 1]!.close) o -= bars[i]!.volume;
    series.push(o);
  }
  return series[series.length - 1]! - series[series.length - 1 - n]!;
}

export interface LiveTick {
  price: number;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
}

/** Thay/ghép nến hôm nay bằng giá trực tiếp. `today` = YYYY-MM-DD (giờ VN). */
export function withLive(bars: Bar[], live: LiveTick | null, today: string): Bar[] {
  if (!live || !Number.isFinite(live.price) || !bars.length) return bars;
  const last = bars[bars.length - 1]!;
  const hi = live.high ?? live.price;
  const lo = live.low ?? live.price;
  if (last.time.slice(0, 10) === today) {
    const b: Bar = {
      ...last,
      close: live.price,
      high: Math.max(last.high, hi, live.price),
      low: Math.min(last.low, lo, live.price),
      volume: live.volume ?? last.volume,
    };
    return [...bars.slice(0, -1), b];
  }
  if (last.time.slice(0, 10) > today) return bars;
  const b: Bar = {
    time: today,
    open: last.close,
    high: Math.max(hi, live.price),
    low: Math.min(lo, live.price),
    close: live.price,
    volume: live.volume ?? 0,
  };
  return [...bars, b];
}

export interface SignalRow {
  id: string;
  name: string;
  group: "ma" | "osc";
  value: string;
  signal: Sig;
  note: string;
}

export type Verdict = "strong_sell" | "sell" | "neutral" | "buy" | "strong_buy";

export interface Gauge {
  buy: number;
  neutral: number;
  sell: number;
  score: number; // -1..1
  verdict: Verdict;
}

export function verdictOf(score: number): Verdict {
  if (score <= -0.5) return "strong_sell";
  if (score <= -0.1) return "sell";
  if (score < 0.1) return "neutral";
  if (score < 0.5) return "buy";
  return "strong_buy";
}

export const VERDICT_VI: Record<Verdict, string> = {
  strong_sell: "Bán mạnh",
  sell: "Bán",
  neutral: "Trung tính",
  buy: "Mua",
  strong_buy: "Mua mạnh",
};

export function gaugeOf(rows: SignalRow[]): Gauge {
  const buy = rows.filter((r) => r.signal === "buy").length;
  const sell = rows.filter((r) => r.signal === "sell").length;
  const neutral = rows.length - buy - sell;
  const score = rows.length ? (buy - sell) / rows.length : 0;
  return { buy, neutral, sell, score, verdict: verdictOf(score) };
}

export interface TaResult {
  bars: number;
  last: number;
  prevClose: number | null;
  rows: SignalRow[];
  ma: Gauge;
  osc: Gauge;
  all: Gauge;
  v: {
    rsi: number | null;
    macd: ReturnType<typeof macd>;
    bb: ReturnType<typeof bollinger>;
    stoch: ReturnType<typeof stochastic>;
    adx: ReturnType<typeof adx>;
    atrPct: number | null;
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
    volRatio: number | null;
    high52: number | null;
    low52: number | null;
    support20: number | null;
    resist20: number | null;
    cross: "golden" | "death" | null;
    obv: number | null;
  };
}

const f = (x: number | null | undefined, d = 2) =>
  x == null || !Number.isFinite(x) ? "—" : x.toLocaleString("vi-VN", { maximumFractionDigits: d, minimumFractionDigits: d });

export function analyze(bars: Bar[]): TaResult | null {
  if (bars.length < 30) return null;
  const close = bars.map((b) => b.close);
  const last = close[close.length - 1]!;
  const rows: SignalRow[] = [];

  const addMa = (id: string, name: string, v: number | null) => {
    if (v == null) return;
    rows.push({
      id,
      name,
      group: "ma",
      value: f(v, 0),
      signal: last > v ? "buy" : last < v ? "sell" : "neutral",
      note: last > v ? "Giá trên đường" : "Giá dưới đường",
    });
  };
  addMa("sma10", "SMA 10", sma(close, 10));
  addMa("sma20", "SMA 20", sma(close, 20));
  addMa("sma50", "SMA 50", sma(close, 50));
  addMa("sma100", "SMA 100", sma(close, 100));
  addMa("sma200", "SMA 200", sma(close, 200));
  addMa("ema12", "EMA 12", ema(close, 12));
  addMa("ema26", "EMA 26", ema(close, 26));

  const rsiV = rsi(close, 14);
  if (rsiV != null)
    rows.push({
      id: "rsi",
      name: "RSI 14",
      group: "osc",
      value: f(rsiV, 1),
      signal: rsiV < 30 ? "buy" : rsiV > 70 ? "sell" : "neutral",
      note: rsiV < 30 ? "Quá bán" : rsiV > 70 ? "Quá mua" : "Vùng trung tính",
    });
  const mc = macd(close);
  if (mc)
    rows.push({
      id: "macd",
      name: "MACD (12,26,9)",
      group: "osc",
      value: f(mc.macd, 2),
      signal: mc.macd > mc.signal && mc.hist > 0 ? "buy" : mc.macd < mc.signal && mc.hist < 0 ? "sell" : "neutral",
      note: mc.hist > 0 ? "MACD trên đường tín hiệu" : "MACD dưới đường tín hiệu",
    });
  const st = stochastic(bars);
  if (st)
    rows.push({
      id: "stoch",
      name: "Stochastic %K (14,3)",
      group: "osc",
      value: f(st.k, 1),
      signal: st.k < 20 ? "buy" : st.k > 80 ? "sell" : "neutral",
      note: st.k < 20 ? "Quá bán" : st.k > 80 ? "Quá mua" : "Vùng trung tính",
    });
  const cc = cci(bars);
  if (cc != null)
    rows.push({
      id: "cci",
      name: "CCI 20",
      group: "osc",
      value: f(cc, 0),
      signal: cc < -100 ? "buy" : cc > 100 ? "sell" : "neutral",
      note: cc < -100 ? "Quá bán" : cc > 100 ? "Quá mua" : "Vùng trung tính",
    });
  const wr = williamsR(bars);
  if (wr != null)
    rows.push({
      id: "wr",
      name: "Williams %R 14",
      group: "osc",
      value: f(wr, 1),
      signal: wr < -80 ? "buy" : wr > -20 ? "sell" : "neutral",
      note: wr < -80 ? "Quá bán" : wr > -20 ? "Quá mua" : "Vùng trung tính",
    });
  const ad = adx(bars);
  if (ad)
    rows.push({
      id: "adx",
      name: "ADX 14 (+DI/−DI)",
      group: "osc",
      value: f(ad.adx, 1),
      signal: ad.adx > 25 ? (ad.pdi > ad.mdi ? "buy" : "sell") : "neutral",
      note: ad.adx > 25 ? (ad.pdi > ad.mdi ? "Xu hướng tăng rõ" : "Xu hướng giảm rõ") : "Xu hướng yếu",
    });
  const bb = bollinger(close);
  if (bb)
    rows.push({
      id: "bb",
      name: "Bollinger %B (20,2)",
      group: "osc",
      value: f(bb.pctB, 2),
      signal: bb.pctB < 0.05 ? "buy" : bb.pctB > 0.95 ? "sell" : "neutral",
      note: bb.pctB < 0.05 ? "Chạm dải dưới" : bb.pctB > 0.95 ? "Chạm dải trên" : "Trong dải",
    });

  const ma = gaugeOf(rows.filter((r) => r.group === "ma"));
  const osc = gaugeOf(rows.filter((r) => r.group === "osc"));
  const all = gaugeOf(rows);

  const s50 = sma(close, 50);
  const s200 = sma(close, 200);
  const pS50 = close.length > 1 ? sma(close.slice(0, -1), 50) : null;
  const pS200 = close.length > 1 ? sma(close.slice(0, -1), 200) : null;
  let cross: "golden" | "death" | null = null;
  // Cắt trong 10 phiên gần nhất
  if (close.length >= 210) {
    for (let k = 0; k < 10; k++) {
      const c = close.slice(0, close.length - k);
      const p = close.slice(0, close.length - k - 1);
      const a = sma(c, 50)! - sma(c, 200)!;
      const b = sma(p, 50)! - sma(p, 200)!;
      if (a > 0 && b <= 0) { cross = "golden"; break; }
      if (a < 0 && b >= 0) { cross = "death"; break; }
    }
  }
  void pS50;
  void pS200;
  const vols = bars.map((b) => b.volume);
  const avg20 = sma(vols.slice(0, -1), 20);
  const a14 = atr(bars);
  const w52 = bars.slice(-252);
  const w20 = bars.slice(-21, -1);
  return {
    bars: bars.length,
    last,
    prevClose: close.length > 1 ? close[close.length - 2]! : null,
    rows,
    ma,
    osc,
    all,
    v: {
      rsi: rsiV,
      macd: mc,
      bb,
      stoch: st,
      adx: ad,
      atrPct: a14 != null && last ? (a14 / last) * 100 : null,
      sma20: sma(close, 20),
      sma50: s50,
      sma200: s200,
      volRatio: avg20 && avg20 > 0 ? vols[vols.length - 1]! / avg20 : null,
      high52: Math.max(...w52.map((b) => b.high)),
      low52: Math.min(...w52.map((b) => b.low)),
      support20: w20.length ? Math.min(...w20.map((b) => b.low)) : null,
      resist20: w20.length ? Math.max(...w20.map((b) => b.high)) : null,
      cross,
      obv: obvTrend(bars),
    },
  };
}

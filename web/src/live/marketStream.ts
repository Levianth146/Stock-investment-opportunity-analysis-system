/**
 * Luồng thị trường trang chủ (017d): 1 EventSource /api/stream/market dùng chung.
 * - full khi kết nối, delta sau đó (seq liên tục; lệch seq → kết nối lại để lấy full).
 * - Mất luồng → poll /api/realtime/market mỗi 30s (dữ liệu cũ nhưng đúng).
 * - Tab ẩn → đóng luồng; hiện lại → mở lại (nhận full mới).
 * - Thông báo cho UI tối đa ~2 lần/giây.
 */
import { api } from "../api/client";
import type { RealtimeMarketResponse } from "../api/types";

export type MarketConn = "idle" | "connecting" | "live" | "fallback";

export interface MarketSnapshot {
  data: RealtimeMarketResponse | null;
  conn: MarketConn;
  /** Số lần cập nhật dữ liệu — dùng để kiểm thử / key hiệu ứng. */
  rev: number;
}

type Candle = { t: number; c: number };
type Msg = Record<string, unknown> & { type?: string; seq?: number };

/** Gộp một tin SSE vào dữ liệu hiện có. Trả null nếu cần kết nối lại (lệch seq). */
export function applyMessage(
  prev: RealtimeMarketResponse | null,
  lastSeq: number,
  msg: Msg,
): { data: RealtimeMarketResponse | null; seq: number } | null {
  if (msg.type === "full") {
    return {
      data: msg.payload as RealtimeMarketResponse,
      seq: Number(msg.seq) || 0,
    };
  }
  if (msg.type === "heartbeat") {
    // seq của heartbeat = seq đã phát; lệch nghĩa là ta đã lỡ tin.
    if (typeof msg.seq === "number" && msg.seq !== lastSeq) return null;
    return { data: prev, seq: lastSeq };
  }
  if (msg.type !== "delta" || !prev) return null;
  const seq = Number(msg.seq);
  if (seq !== lastSeq + 1) return null;

  const next: RealtimeMarketResponse = { ...prev };
  for (const k of ["label", "session", "realtime", "as_of_ts", "breadth", "lists"] as const) {
    if (k in msg) (next as unknown as Record<string, unknown>)[k] = msg[k];
  }
  if (msg.index && typeof msg.index === "object") {
    const inc = msg.index as Record<string, unknown> & {
      candles_tail?: Candle[];
      candles_count?: number;
    };
    const { candles_tail, candles_count, ...rest } = inc;
    void candles_count;
    const old = prev.index || {};
    let candles = [...(old.candles_1m || [])];
    for (const c of candles_tail || []) {
      const i = candles.findIndex((x) => x.t === c.t);
      if (i >= 0) candles[i] = c;
      else candles.push(c);
    }
    candles = candles.sort((a, b) => a.t - b.t);
    next.index = { ...old, ...rest, candles_1m: candles, series_eod: old.series_eod };
  }
  if (Array.isArray(msg.heatmap) && prev.heatmap) {
    const upd = new Map<string, [number | null, string | null, string | null]>();
    for (const row of msg.heatmap as Array<[string, number | null, string | null, string | null]>) {
      upd.set(row[0], [row[1], row[2], row[3]]);
    }
    next.heatmap = prev.heatmap.map((h) => {
      const u = upd.get(h.symbol);
      if (!u) return h;
      return {
        ...h,
        change_pct: { ...h.change_pct, value: u[0], basis: u[2] ?? h.change_pct?.basis },
        label: u[1],
      };
    });
  }
  return { data: next, seq };
}

const NOTIFY_MS = 500; // ≤2 lần/giây
const POLL_MS = 30_000;
const RECONNECT_MIN = 1_000;
const RECONNECT_MAX = 30_000;

export class MarketStream {
  private snap: MarketSnapshot = { data: null, conn: "idle", rev: 0 };
  private subs = new Set<() => void>();
  private refs = 0;
  private es: EventSource | null = null;
  private seq = 0;
  private backoff = RECONNECT_MIN;
  private retryT: number | undefined;
  private pollT: number | undefined;
  private notifyT: number | undefined;
  private visHandler = () => this.onVisibility();

  constructor(
    private readonly url = "/api/stream/market",
    private readonly fetchFull: () => Promise<RealtimeMarketResponse> = () => api.realtimeMarket(),
    private readonly ES: typeof EventSource | undefined = typeof EventSource !== "undefined"
      ? EventSource
      : undefined,
  ) {}

  subscribe = (fn: () => void) => {
    this.subs.add(fn);
    return () => this.subs.delete(fn);
  };
  getSnapshot = () => this.snap;

  /** Giữ luồng mở khi có component cần; trả hàm nhả. */
  retain(): () => void {
    this.refs += 1;
    if (this.refs === 1) this.start();
    let done = false;
    return () => {
      if (done) return;
      done = true;
      this.refs -= 1;
      if (this.refs === 0) this.stop();
    };
  }

  private set(patch: Partial<MarketSnapshot>, immediate = false) {
    this.snap = { ...this.snap, ...patch };
    if (immediate) {
      this.flush();
      return;
    }
    if (this.notifyT === undefined) {
      this.notifyT = window.setTimeout(() => this.flush(), NOTIFY_MS);
    }
  }

  private flush() {
    if (this.notifyT !== undefined) {
      clearTimeout(this.notifyT);
      this.notifyT = undefined;
    }
    this.subs.forEach((f) => f());
  }

  private start() {
    document.addEventListener("visibilitychange", this.visHandler);
    if (document.visibilityState !== "hidden") this.open();
    // Dữ liệu ban đầu ngay cả khi SSE chưa kịp mở.
    void this.pollOnce();
  }

  private stop() {
    document.removeEventListener("visibilitychange", this.visHandler);
    this.close();
    clearTimeout(this.pollT);
    this.pollT = undefined;
    this.set({ conn: "idle" }, true);
  }

  private onVisibility() {
    if (this.refs === 0) return;
    if (document.visibilityState === "hidden") {
      this.close();
      clearTimeout(this.pollT);
      this.pollT = undefined;
    } else {
      this.open(); // nhận full mới khi quay lại tab
      void this.pollOnce();
    }
  }

  private close() {
    clearTimeout(this.retryT);
    this.retryT = undefined;
    if (this.es) {
      this.es.close();
      this.es = null;
    }
  }

  private open() {
    this.close();
    if (!this.ES) {
      this.set({ conn: "fallback" }, true);
      return;
    }
    if (this.snap.conn !== "live") this.set({ conn: "connecting" }, true);
    let es: EventSource;
    try {
      es = new this.ES(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.es = es;
    es.onmessage = (ev) => {
      let msg: Msg;
      try {
        msg = JSON.parse(ev.data) as Msg;
      } catch {
        return;
      }
      const res = applyMessage(this.snap.data, this.seq, msg);
      if (res === null) {
        this.close();
        this.open(); // lệch seq → xin full mới
        return;
      }
      this.backoff = RECONNECT_MIN;
      const changed = res.data !== this.snap.data;
      this.seq = res.seq;
      clearTimeout(this.pollT);
      this.pollT = undefined;
      this.set(
        {
          data: res.data,
          conn: "live",
          rev: changed ? this.snap.rev + 1 : this.snap.rev,
        },
        msg.type === "full",
      );
    };
    es.onerror = () => {
      if (this.es !== es) return;
      this.close();
      this.set({ conn: "fallback" }, true);
      this.schedulePoll();
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect() {
    clearTimeout(this.retryT);
    const wait = this.backoff;
    this.backoff = Math.min(this.backoff * 2, RECONNECT_MAX);
    this.retryT = window.setTimeout(() => {
      if (this.refs > 0 && document.visibilityState !== "hidden") this.open();
    }, wait);
  }

  private schedulePoll() {
    clearTimeout(this.pollT);
    this.pollT = window.setTimeout(() => void this.pollOnce(), POLL_MS);
  }

  private async pollOnce() {
    if (this.refs === 0) return;
    // Đang có luồng sống thì không cần poll.
    if (this.snap.conn === "live" && this.snap.data) return;
    try {
      const data = await this.fetchFull();
      if (this.snap.conn !== "live") {
        this.set({ data, rev: this.snap.rev + 1 }, true);
      }
    } catch {
      /* giữ dữ liệu cũ */
    }
    if (this.snap.conn !== "live" && this.refs > 0) this.schedulePoll();
  }
}

export const marketStream = new MarketStream();

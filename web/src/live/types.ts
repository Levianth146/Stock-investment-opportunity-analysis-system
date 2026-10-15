/** Kiểu quote / trạng thái hiển thị realtime. */

export type QuoteState =
  | "live"
  | "stale"
  | "closed"
  | "no_realtime"
  | "unit_mismatch";

export interface LiveQuote {
  symbol: string;
  price: number | null;
  prev_close: number | null;
  prev_close_source?: string | null;
  change: number | null;
  change_pct: number | null;
  volume?: number | null;
  high?: number | null;
  low?: number | null;
  ts?: string | null;
  state: QuoteState | string;
  basis?: string;
  source?: string;
  label?: string | null;
  ref_label?: string | null;
  /** Thời điểm nhận tại client (performance.now / monotonic proxy) */
  receivedAt?: number;
}

export interface LiveStatus {
  mode: string;
  state: QuoteState | string;
  banner: string | null;
  sessionPhase?: string | null;
  /** Lý do no_realtime từ /api/realtime/status (không chứa secrets). */
  reason?: string | null;
}

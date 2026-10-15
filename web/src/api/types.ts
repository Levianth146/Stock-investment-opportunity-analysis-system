/** Kiểu phản hồi API — viết tay từ contract thật (feature 011/014). */

export type Profile = "long_term" | "swing";

export interface ApiEnvelope {
  asof: string | null;
  disclaimer: string;
}

export interface ApiErrorBody extends ApiEnvelope {
  error: string;
  detail?: string;
}

export interface MetaResponse extends ApiEnvelope {
  profiles: Profile[];
  default_profile: Profile;
  universe_count: number;
  scored_count: number;
  formula: string;
  risk_reference?: number;
  /** Ngưỡng khuyến nghị nếu API trả (014c đọc nếu có). */
  ratings?: Array<{ min: number; label: string }>;
  scoring?: {
    profiles?: Record<
      string,
      { weights: Record<string, number>; lambda_R: number }
    >;
    risk_reference?: number;
    ratings?: Array<{ min: number; label: string }>;
    risk_gate?: { R_threshold: number; max_rating: string };
    data_gate?: {
      limited_max_rating?: string;
      implausible_upside_pct?: number;
      implausible_max_rating?: string;
    };
  };
  llm?: LlmStatus;
}

export interface LlmStatus {
  state?: "ok" | "quota_blocked" | "circuit_open" | "no_key" | string;
  retry_after?: number | null;
  provider?: string | null;
  model?: string | null;
  key_configured?: boolean;
  blocked_until?: string | null;
  blocked_until_local?: string | null;
  [k: string]: unknown;
}

export interface RankingScores {
  F: number | null;
  T: number | null;
  V: number | null;
  S: number | null;
  R: number | null;
}

export interface RankingSignals {
  above_ma50?: boolean | null;
  above_ma200?: boolean | null;
  rsi_zone?: "overbought" | "oversold" | "neutral" | null;
  volume_up?: boolean | null;
}

export interface RankingRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  exchange?: string | null;
  score: number | null;
  rating: string;
  scores: RankingScores;
  price?: number | null;
  reference_price?: number | null;
  upside_pct?: number | null;
  market_cap?: number | null;
  signals?: RankingSignals;
  rewards_count?: number | null;
  risks_count?: number | null;
  ranked: boolean;
  quality_gate?: {
    tier?: string;
    scored?: boolean;
    reasons?: string[];
  };
}

export interface RankingsResponse extends ApiEnvelope {
  total: number;
  /** Số mã đã chấm điểm trong profile (không phụ thuộc limit/offset/lọc). */
  total_scored?: number;
  items: RankingRow[];
}

export interface HealthResponse extends ApiEnvelope {
  status: "ok" | "warming" | string;
}

export interface SectorItem {
  sector: string;
  label: string;
  count: number;
  n_scored?: number;
  mean_score?: number | null;
  median_score?: number | null;
  rating_distribution?: Record<string, number>;
  mean_pillars?: RankingScores;
}

export interface SectorsResponse extends ApiEnvelope {
  profile?: Profile;
  items: SectorItem[];
}

export interface PillarRankEntry {
  percentile?: number;
  top_pct?: number;
  n?: number;
  value?: number;
}

export interface TickerDetailResponse extends ApiEnvelope {
  symbol: string;
  profile: Profile;
  company: {
    name?: string | null;
    sector?: string | null;
    exchange?: string | null;
    is_bank?: boolean;
    shares_outstanding?: number | null;
  } | null;
  result: {
    ticker?: string;
    score?: number | null;
    rating?: string;
    scores?: RankingScores;
    contributions?: RankingScores;
    target?: {
      base?: number;
      bull?: number;
      bear?: number;
      method?: string;
      assumptions?: string[];
    } | null;
    bull?: Array<{ text: string; refs?: string[] }>;
    bear?: Array<{ text: string; refs?: string[] }>;
    quality_gate?: {
      tier?: string;
      scored?: boolean;
      reasons?: string[];
    };
    flags?: string[];
  };
  modules: Record<
    string,
    {
      status?: string;
      score?: number | null;
      metrics?: Record<string, unknown>;
      flags?: string[];
    }
  >;
  validation?: unknown;
  quality_gate?: {
    tier?: string;
    scored?: boolean;
    reasons?: string[];
  };
  pillar_rank?: {
    F?: PillarRankEntry | null;
    T?: PillarRankEntry | null;
    V?: PillarRankEntry | null;
    S?: PillarRankEntry | null;
    safety?: PillarRankEntry | null;
    n_sector_scored?: number;
  };
  checks_summary?: {
    rewards_count?: number;
    risks_count?: number;
    f_score?: { x?: number; y?: number; label?: string | null; hide?: boolean };
  };
}

export interface CheckItem {
  id: string;
  side?: string;
  label_vi?: string;
  basis?: string;
  source?: string;
  family?: string;
  passed?: boolean | null;
  value?: unknown;
  display?: string | null;
  na?: boolean;
}

export interface ChecksResponse extends ApiEnvelope {
  symbol: string;
  profile?: Profile;
  is_bank?: boolean;
  checks: CheckItem[];
  rewards: CheckItem[];
  rewards_failed: CheckItem[];
  not_met?: CheckItem[];
  risks: CheckItem[];
  risks_failed: CheckItem[];
  cleared_risks?: CheckItem[];
  info?: CheckItem[];
  rewards_count: number;
  risks_count: number;
  cleared_risks_count?: number;
  f_score?: { x?: number; y?: number; label?: string | null; hide?: boolean };
  method?: string;
  basis_tooltip?: Record<string, string>;
}

export interface QuarterSummaryResponse extends ApiEnvelope {
  symbol: string;
  available: boolean;
  period?: string | null;
  items?: Record<
    string,
    { value: number | null; yoy: number | null; qoq: number | null }
  >;
  published_at?: string | null;
  published_estimated?: boolean | null;
  price_reaction?: {
    t0?: string;
    close_before?: number;
    close_after_1d?: number;
    return_1d?: number | null;
    return_5d?: number | null;
  } | null;
  price_reaction_reason?: string | null;
  is_bank?: boolean;
}

export interface SnapshotStatItem {
  id: string;
  label_vi?: string;
  value: number | null;
  unit?: string;
  tone?: "good" | "neutral" | "bad" | string;
}

export interface SnapshotStatsResponse extends ApiEnvelope {
  symbol: string;
  profile?: Profile;
  items: SnapshotStatItem[];
  is_bank?: boolean;
}

export interface OhlcvBar {
  time: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface IndicatorPoint {
  time: string;
  value: number | null;
}

export interface PricesResponse extends ApiEnvelope {
  symbol: string;
  range: string;
  ohlcv: OhlcvBar[];
  ma20?: number | null;
  ma50?: number | null;
  index?: {
    symbol?: string;
    series: Array<{ time: string; close: number | null }> | null;
    note?: string | null;
  };
  indicators?: {
    ma20: IndicatorPoint[];
    ma50: IndicatorPoint[];
    ma200: IndicatorPoint[];
    rsi14: IndicatorPoint[];
    macd: IndicatorPoint[];
    signal: IndicatorPoint[];
    hist: IndicatorPoint[];
  };
}

export interface NewsItem {
  id: string;
  title?: string | null;
  label?: string;
  source?: string | null;
  url?: string | null;
  published_at?: string | null;
}

export interface NewsResponse extends ApiEnvelope {
  symbol: string;
  items: NewsItem[];
  other_items?: NewsItem[];
  latest_news_date?: string | null;
  total_news?: number;
}

export interface DebateAiAttempt {
  state: "ok" | "failed" | "skipped" | string;
  reason_code?: string | null;
  retry_after?: number | null;
}

export interface DebateResponse extends ApiEnvelope {
  symbol?: string;
  profile?: Profile;
  source: "cache" | "template" | "live" | string;
  bull: Array<{ text: string; refs?: string[] }>;
  bear: Array<{ text: string; refs?: string[] }>;
  model?: string | null;
  provider?: string | null;
  created_at?: string | null;
  rate_limited?: boolean;
  message?: string | null;
  reason?: string | null;
  /** Số lượt AI còn lại trong cửa sổ giờ (nếu API trả). */
  quota_remaining?: number | null;
  ai_attempt?: DebateAiAttempt | null;
  [k: string]: unknown;
}

export interface DebateJobCreateResponse extends ApiEnvelope {
  job_id: string;
  state: "queued" | "running" | string;
  symbol?: string;
  profile?: Profile;
  attempt?: number;
}

export interface DebateJobStatusResponse extends ApiEnvelope {
  job_id: string;
  state: "queued" | "running" | "ok" | "failed" | string;
  symbol?: string;
  profile?: Profile;
  attempt?: number;
  reason_code?: string | null;
  retry_after?: number | null;
  result?: DebateResponse | null;
}

export interface FinancialPeriod {
  period: string | number;
  published_at?: string | null;
  items: Record<string, number | null>;
  gross_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roe_basis?: string | null;
  debt_to_equity: number | null;
  fcf: number | null;
  revenue_yoy?: number | null;
  net_income_yoy?: number | null;
  revenue_qoq?: number | null;
  flags?: string[];
}

export interface FinancialsResponse extends ApiEnvelope {
  symbol: string;
  meta: {
    unit: string;
    unit_note?: string;
    roe_basis?: string;
    fcf_note?: string;
  };
  annual: FinancialPeriod[];
  quarterly: FinancialPeriod[];
}

/** GET /api/tickers/{symbol}/income-flow (017c). */
export interface IncomeFlowNode {
  id: string;
  label: string;
  kind: string;
  derived?: boolean;
  value: number;
  pct_revenue: number | null;
}

export interface IncomeFlowLink {
  source: string;
  target: string;
  value: number;
  pct_revenue: number | null;
}

export interface IncomeFlowSummary {
  gross_margin: number | null;
  net_margin: number | null;
  expense_to_revenue: number | null;
  gross_margin_prior: number | null;
  net_margin_prior: number | null;
  expense_to_revenue_prior: number | null;
  prior_label?: string;
}

export interface IncomeFlowResponse extends ApiEnvelope {
  symbol: string;
  period: string;
  unit?: string;
  supported: boolean;
  message?: string;
  revenue?: number;
  npat?: number;
  loss?: boolean;
  nodes: IncomeFlowNode[];
  links: IncomeFlowLink[];
  notes: string[];
  conservation_ok?: boolean;
  available_periods: string[];
  summary?: IncomeFlowSummary | null;
}

export interface PeerRow {
  ticker: string;
  is_self?: boolean;
  pe: number | null;
  pb: number | null;
  roe: number | null;
  market_cap: number | null;
}

export interface PercentileBand {
  p10: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p90: number | null;
}

export interface PeersResponse extends ApiEnvelope {
  symbol: string;
  sector?: string | null;
  items: PeerRow[];
  sector_medians: {
    sector?: string | null;
    median_pe?: number | null;
    median_pb?: number | null;
    n_pe?: number | null;
    n_pb?: number | null;
    pe_band?: PercentileBand | null;
    pb_band?: PercentileBand | null;
  };
}

export interface MarketIndex {
  symbol: string;
  close: number | null;
  change_pct: number | null;
  asof_session?: string | null;
  series_30d: Array<{ time: string; close: number | null }>;
}

export interface MarketResponse extends ApiEnvelope {
  index: MarketIndex | null;
  flags?: string[];
}

export interface RealtimeMarketResponse extends ApiEnvelope {
  as_of_ts?: string;
  label?: string;
  session?: { phase?: string; as_of_ts?: string };
  realtime?: { mode?: string; state?: string };
  index?: {
    symbol?: string;
    name?: string;
    price?: { value?: number | null; basis?: string };
    prev_close?: { value?: number | null };
    change_pct?: { value?: number | null };
    candles_1m?: Array<{ t: number; c: number }>;
    series_eod?: Array<{ time: string; close: number | null }>;
    available?: string[];
    label?: string;
    source?: string;
  };
  breadth?: Record<string, unknown>;
  lists?: Record<string, unknown>;
  heatmap?: Array<{
    symbol: string;
    sector: string;
    change_pct?: { value?: number | null; basis?: string | null };
    market_cap?: { value?: number | null };
    market_cap_ref?: number | null;
    label?: string | null;
  }>;
}

export interface CompanyProfile {
  symbol: string;
  name?: string | null;
  short_name?: string | null;
  intro?: string | null;
  listing_date?: string | null;
  first_price?: number | null;
  state_pct?: number | null;
  foreign_pct?: number | null;
  foreign_max_pct?: number | null;
  free_float_pct?: number | null;
  issue_share?: number | null;
  source?: string;
  data_date?: string;
}

export interface CompanyProfileResponse extends ApiEnvelope {
  symbol: string;
  available: boolean;
  profile: CompanyProfile | null;
}

export interface DividendEvent {
  ex_date: string | null;
  record_date?: string | null;
  pay_date?: string | null;
  kind: "cash" | "stock" | string;
  percent_of_par?: number | null;
  dps_vnd?: number | null;
  title?: string | null;
}

export interface DividendsResponse extends ApiEnvelope {
  symbol: string;
  available: boolean;
  reason?: string;
  events: DividendEvent[];
  dps_ttm_vnd?: number | null;
  source?: string | null;
  fetched_at?: string | null;
}

export interface WatchlistItem {
  symbol: string;
  name?: string | null;
  sector?: string | null;
  price?: { value?: number | null; basis?: string };
  change_pct?: { value?: number | null };
  score?: number | null;
  rank?: number | null;
  total_scored?: number | null;
  dividend_yield?: { value?: number | null };
  sector_ref?: {
    value?: number | null;
    gap_pct?: number | null;
    unreliable?: boolean;
    label?: string | null;
  };
  state?: string;
  label?: string;
  data_asof?: string;
}

export interface WatchlistSummaryResponse extends ApiEnvelope {
  profile?: Profile;
  items: WatchlistItem[];
  label?: string;
}

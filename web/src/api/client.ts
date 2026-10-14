/** Client HTTP cho /api — envelope, lỗi, 429 Retry-After. */

import type {
  ApiEnvelope,
  ApiErrorBody,
  DebateJobCreateResponse,
  DebateJobStatusResponse,
  DebateResponse,
  FinancialsResponse,
  HealthResponse,
  LlmStatus,
  MarketResponse,
  MetaResponse,
  NewsResponse,
  ChecksResponse,
  PeersResponse,
  PricesResponse,
  Profile,
  QuarterSummaryResponse,
  RankingsResponse,
  SectorsResponse,
  SnapshotStatsResponse,
  TickerDetailResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;
  retryAfterSec: number | null;

  constructor(
    message: string,
    status: number,
    body: ApiErrorBody | null = null,
    retryAfterSec: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.retryAfterSec = retryAfterSec;
  }
}

function parseRetryAfter(h: string | null): number | null {
  if (!h) return null;
  const n = Number(h);
  if (!Number.isNaN(n)) return n;
  const when = Date.parse(h);
  if (!Number.isNaN(when)) {
    return Math.max(0, Math.ceil((when - Date.now()) / 1000));
  }
  return null;
}

async function request<T>(
  path: string,
  init?: RequestInit & { searchParams?: Record<string, string | number | boolean | undefined | null> },
): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (init?.searchParams) {
    for (const [k, v] of Object.entries(init.searchParams)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  const { searchParams: _sp, ...rest } = init || {};
  const res = await fetch(url.toString(), {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(rest.headers || {}),
    },
  });

  const retryAfter = parseRetryAfter(res.headers.get("Retry-After"));
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (res.status === 429) {
    const errBody = (body || {}) as ApiErrorBody;
    throw new ApiError(
      errBody.error || "Quá nhiều yêu cầu — thử lại sau.",
      429,
      errBody,
      retryAfter,
    );
  }

  if (!res.ok) {
    const errBody = (body || {}) as ApiErrorBody;
    throw new ApiError(
      errBody.error || `Lỗi ${res.status}`,
      res.status,
      errBody,
      retryAfter,
    );
  }

  return body as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),

  meta: () => request<MetaResponse>("/api/meta"),

  llmStatus: () => request<LlmStatus & ApiEnvelope>("/api/llm/status"),

  rankings: (params: {
    profile?: Profile;
    sector?: string;
    rating?: string;
    q?: string;
    sort?: string;
    order?: "asc" | "desc";
    limit?: number; // API tối đa 2000
    offset?: number;
    include_unranked?: boolean;
  }) =>
    request<RankingsResponse>("/api/rankings", { searchParams: params }),

  sectors: (profile?: Profile) =>
    request<SectorsResponse>("/api/sectors", {
      searchParams: { profile },
    }),

  market: () => request<MarketResponse>("/api/market"),

  ticker: (symbol: string, profile?: Profile) =>
    request<TickerDetailResponse>(`/api/tickers/${encodeURIComponent(symbol)}`, {
      searchParams: { profile },
    }),

  prices: (
    symbol: string,
    params?: {
      range?: string;
      profile?: Profile;
      include_index?: boolean;
      include_indicators?: boolean;
    },
  ) =>
    request<PricesResponse>(`/api/tickers/${encodeURIComponent(symbol)}/prices`, {
      searchParams: params,
    }),

  news: (symbol: string, profile?: Profile) =>
    request<NewsResponse>(`/api/tickers/${encodeURIComponent(symbol)}/news`, {
      searchParams: { profile },
    }),

  financials: (symbol: string) =>
    request<FinancialsResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/financials`,
    ),

  peers: (symbol: string) =>
    request<PeersResponse>(`/api/tickers/${encodeURIComponent(symbol)}/peers`),

  checks: (symbol: string, profile?: Profile) =>
    request<ChecksResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/checks`,
      { searchParams: { profile } },
    ),

  quarterSummary: (symbol: string) =>
    request<QuarterSummaryResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/quarter-summary`,
    ),

  snapshotStats: (symbol: string, profile?: Profile) =>
    request<SnapshotStatsResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/snapshot-stats`,
      { searchParams: { profile } },
    ),

  debate: (symbol: string, profile?: Profile, refresh = false) =>
    request<DebateResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/debate`,
      {
        method: "POST",
        searchParams: { profile, refresh },
      },
    ),

  debateJobCreate: (symbol: string, profile?: Profile) =>
    request<DebateJobCreateResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/debate/jobs`,
      {
        method: "POST",
        searchParams: { profile },
      },
    ),

  debateJobGet: (symbol: string, jobId: string, profile?: Profile) =>
    request<DebateJobStatusResponse>(
      `/api/tickers/${encodeURIComponent(symbol)}/debate/jobs/${encodeURIComponent(jobId)}`,
      { searchParams: { profile } },
    ),

  reportPdfUrl: (symbol: string, profile?: Profile) => {
    const q = new URLSearchParams();
    if (profile) q.set("profile", profile);
    const qs = q.toString();
    return `/api/report/${encodeURIComponent(symbol)}.pdf${qs ? `?${qs}` : ""}`;
  },
};

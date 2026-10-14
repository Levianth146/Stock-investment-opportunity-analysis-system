import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import type {
  CheckItem,
  DebateResponse,
  Profile,
  TickerDetailResponse,
} from "../api/types";
import { ContributionBars } from "../components/ContributionBars";
import { PillarRadar } from "../components/PillarRadar";
import { ScoreRuler } from "../components/ScoreRuler";
import { OverviewPriceChart } from "../charts/OverviewPriceChart";
import { TechnicalChart } from "../charts/TechnicalChart";
import { DividendPanel } from "../charts/DividendCharts";
import { AnnualFinCharts, QuarterlyFinCharts } from "../charts/FinCharts";
import { IncomeFlowPanel } from "../charts/IncomeSankey";
import { ValuationCharts } from "../charts/ValuationCharts";
import { buildConclusion } from "../conclusion";
import { cleanDebateItems } from "../debateText";
import {
  debateFailLine,
  debateSourceLabel,
  viJobFailReason,
} from "../debateUi";
import { compactBillions, dateVi, num, pct, score, vnd } from "../fmt";
import { FIN_UNIT_ROE_NOTE } from "../finNotes";
import { rankAmongScored } from "../rank";
import { ratingsFromMeta } from "../ratings";
import { evaluateRefPrice } from "../refPrice";
import { buildRiskOpportunity } from "../riskOpportunity";
import { sectorVi } from "../sectors";
import { showToast } from "../toast";
import { buildIncomeBridge, sumPeriodItems } from "../waterfall";

type Tab =
  | "overview"
  | "valuation"
  | "growth"
  | "health"
  | "dividend"
  | "technical"
  | "news";

const TABS: { id: Tab; label: string; question: string }[] = [
  { id: "overview", label: "Tổng quan", question: "Mã này đáng xem ở mức nào?" },
  { id: "valuation", label: "Định giá", question: "Giá có hấp dẫn?" },
  { id: "growth", label: "Tăng trưởng", question: "Doanh thu và lợi nhuận đang đi đâu?" },
  {
    id: "health",
    label: "Sức khỏe tài chính",
    question: "Bảng cân đối và dòng tiền ổn không?",
  },
  { id: "dividend", label: "Cổ tức", question: "Công ty trả cổ tức thế nào?" },
  { id: "technical", label: "Kỹ thuật", question: "Xu hướng giá đang ra sao?" },
  { id: "news", label: "Tin tức", question: "Tin gần đây nói gì?" },
];

function metricNum(
  metrics: Record<string, unknown> | undefined,
  key: string,
): number | null {
  const raw = metrics?.[key];
  if (typeof raw === "number") return raw;
  if (raw && typeof raw === "object" && "value" in raw) {
    const v = (raw as { value?: unknown }).value;
    return typeof v === "number" ? v : null;
  }
  return null;
}

function CheckTable({
  items,
  tip,
  empty,
  muted,
}: {
  items: CheckItem[];
  tip: Record<string, string>;
  empty: string;
  muted?: boolean;
}) {
  if (!items.length) {
    return empty ? <p className="muted">{empty}</p> : null;
  }
  return (
    <table className={`check-table${muted ? " muted" : ""}`}>
      <thead>
        <tr>
          <th scope="col">Phép kiểm</th>
          <th scope="col">Nguồn</th>
        </tr>
      </thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.id} title={tip[c.basis || ""] || c.source || undefined}>
            <td>{c.label_vi}</td>
            <td className="muted">{c.source || tip[c.basis || ""] || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

async function downloadPdf(symbol: string, profile: Profile) {
  const url = api.reportPdfUrl(symbol, profile);
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    const href = URL.createObjectURL(blob);
    a.href = href;
    a.download = `${symbol}_${profile}.pdf`;
    a.click();
    URL.revokeObjectURL(href);
    showToast("Đã tạo PDF");
  } catch {
    showToast("Không tạo được PDF — thử lại sau");
  }
}

export function TickerPage() {
  const { symbol: raw } = useParams();
  const symbol = (raw || "").toUpperCase();
  const [sp, setSp] = useSearchParams();
  const profile = (sp.get("profile") as Profile) || "long_term";
  const tab = (sp.get("tab") as Tab) || "overview";
  const tablistRef = useRef<HTMLDivElement>(null);

  const setTab = (t: Tab) => {
    const n = new URLSearchParams(sp);
    n.set("tab", t);
    setSp(n, { replace: true });
  };

  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const idx = TABS.findIndex((t) => t.id === tab);
    if (idx < 0) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const nextIdx =
        e.key === "ArrowRight"
          ? (idx + 1) % TABS.length
          : (idx - 1 + TABS.length) % TABS.length;
      const next = TABS[nextIdx];
      if (!next) return;
      setTab(next.id);
      requestAnimationFrame(() => {
        tablistRef.current
          ?.querySelector<HTMLButtonElement>(`[data-tab="${next.id}"]`)
          ?.focus();
      });
    }
  };

  const metaQ = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const ratings = ratingsFromMeta(metaQ.data);

  const detail = useQuery({
    queryKey: ["ticker", symbol, profile],
    queryFn: () => api.ticker(symbol, profile),
    enabled: !!symbol,
  });

  const rankingsQ = useQuery({
    queryKey: ["rankings-all", profile],
    queryFn: () =>
      api.rankings({
        profile,
        limit: 500,
        include_unranked: false,
        sort: "score",
        order: "desc",
      }),
  });

  const sectorsQ = useQuery({
    queryKey: ["sectors", profile],
    queryFn: () => api.sectors(profile),
  });

  const result = detail.data?.result;
  const unranked = result?.quality_gate?.scored === false || result?.score == null;
  const priceClose = useMemo(() => {
    const m = detail.data?.modules?.m4?.metrics as Record<string, unknown> | undefined;
    return metricNum(m, "price_close");
  }, [detail.data]);
  const refRaw = result?.target?.base ?? null;
  const refView = evaluateRefPrice(priceClose, refRaw);

  const rankInfo = useMemo(() => {
    const totalScored =
      rankingsQ.data?.total_scored ??
      metaQ.data?.scored_count ??
      rankingsQ.data?.total ??
      null;
    return rankAmongScored(rankingsQ.data?.items, symbol, totalScored);
  }, [rankingsQ.data, metaQ.data?.scored_count, symbol]);

  const sectorMedian = useMemo(() => {
    const sec = detail.data?.company?.sector;
    if (!sec) return null;
    const hit = (sectorsQ.data?.items || []).find((s) => s.sector === sec);
    if (!hit) return null;
    const n = hit.n_scored ?? hit.count ?? 0;
    if (n < 5) return null;
    return hit.median_score ?? null;
  }, [detail.data, sectorsQ.data]);

  const pricesHeaderQ = useQuery({
    queryKey: ["prices-header", symbol],
    queryFn: () =>
      api.prices(symbol, { range: "1y", include_indicators: false }),
    enabled: !!symbol && !!detail.data,
  });

  const keyData = useMemo(() => {
    if (!detail.data) return [];
    return buildHeaderKeyData(detail.data, priceClose, pricesHeaderQ.data);
  }, [detail.data, priceClose, pricesHeaderQ.data]);

  const conclusion = buildConclusion({
    rating: result?.rating,
    score: result?.score ?? null,
    rank: rankInfo.rank,
    n: rankInfo.n,
    scores: result?.scores,
    unranked,
    unrankedReason: (result?.quality_gate?.reasons || []).join("; "),
  });

  const rulerMarkers = useMemo(() => {
    const m: { value: number; label: string; kind: "primary" | "secondary" }[] = [];
    if (result?.score != null) {
      m.push({ value: result.score, label: symbol, kind: "primary" });
    }
    if (sectorMedian != null) {
      m.push({
        value: sectorMedian,
        label: `Trung vị ngành ${score(sectorMedian)}`,
        kind: "secondary",
      });
    }
    return m;
  }, [result?.score, sectorMedian, symbol]);

  return (
    <main>
      <p style={{ margin: "0 0 8px" }}>
        <Link to={`/?profile=${profile}`}>Bảng xếp hạng</Link>
      </p>

      {detail.isLoading && <div className="skeleton" aria-busy="true" />}
      {detail.isError && (
        <div className="error-box" role="alert">
          {(detail.error as ApiError)?.message || "Không tải được mã."} Thử lại
          hoặc quay về bảng xếp hạng.
        </div>
      )}

      {detail.data && (
        <>
          <header className="ticker-header">
            <div className="ticker-header-line1">
              <h1>
                {symbol}
                <span className="company-name">{detail.data.company?.name}</span>
              </h1>
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <label>
                  <span className="muted">Kiểu đầu tư </span>
                  <select
                    value={profile}
                    onChange={(e) => {
                      const n = new URLSearchParams(sp);
                      n.set("profile", e.target.value);
                      setSp(n, { replace: true });
                    }}
                    aria-label="Kiểu đầu tư"
                  >
                    <option value="long_term">Dài hạn</option>
                    <option value="swing">Lướt sóng</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="pdf-link"
                  onClick={() => downloadPdf(symbol, profile)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <path d="M12 3v12" />
                    <path d="M7 10l5 5 5-5" />
                    <path d="M5 21h14" />
                  </svg>
                  Tải PDF
                </button>
              </div>
            </div>

            <p className="conclusion">{conclusion}</p>

            <div className="ticker-sector">{sectorVi(detail.data.company?.sector)}</div>

            {!unranked && rulerMarkers.length > 0 && (
              <ScoreRuler
                ratings={ratings}
                markers={rulerMarkers}
                animatePrimary
                aria-label={`Thước điểm ${symbol}`}
              />
            )}

            <div className="key-data" aria-label="Chỉ số chính">
              {keyData.map((s) => (
                <div className="kd" key={s.label}>
                  <label>{s.label}</label>
                  <strong className="tabular">{s.value}</strong>
                </div>
              ))}
            </div>

            {refView.unreliable && (
              <p className="muted caution" title={refView.tooltip ?? undefined}>
                Chênh lệch giá tham chiếu theo ngành quá lớn so với giá hiện tại — không
                đáng tin cậy.
              </p>
            )}
          </header>

          <div
            className="tabs"
            role="tablist"
            aria-label="Phần chi tiết mã"
            ref={tablistRef}
            onKeyDown={onTabKey}
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                data-tab={t.id}
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <p className="tab-question muted prose">
            {TABS.find((t) => t.id === tab)?.question}
          </p>

          <div
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
          >
            {tab === "overview" && (
              <OverviewTab symbol={symbol} profile={profile} detail={detail.data} />
            )}
            {tab === "valuation" && (
              <ValuationTab
                symbol={symbol}
                profile={profile}
                detail={detail.data}
                priceClose={priceClose}
                refDisplay={refView.display}
              />
            )}
            {(tab === "growth" || tab === "health" || tab === "dividend") && (
              <FinancialsTab
                symbol={symbol}
                mode={tab}
                isBank={
                  !!detail.data.company?.is_bank ||
                  String(detail.data.company?.sector || "")
                    .toLowerCase()
                    .includes("bank")
                }
              />
            )}
            {tab === "technical" && (
              <TechnicalTab symbol={symbol} profile={profile} />
            )}
            {tab === "news" && <NewsTab symbol={symbol} profile={profile} />}
          </div>
        </>
      )}
    </main>
  );
}

function buildHeaderKeyData(
  detail: TickerDetailResponse,
  priceClose: number | null,
  prices: Awaited<ReturnType<typeof api.prices>> | undefined,
): { label: string; value: string }[] {
  const shares = detail.company?.shares_outstanding ?? null;
  const m6 = detail.modules?.m6?.metrics as Record<string, unknown> | undefined;
  const beta = metricNum(m6, "beta");
  const mcap =
    shares != null && priceClose != null && shares > 0 && priceClose > 0
      ? (shares * priceClose) / 1e9
      : null;

  let avgVol: number | null = null;
  let range52 = "—";
  if (prices?.ohlcv?.length) {
    const recent = prices.ohlcv.slice(-22);
    const vols = recent
      .map((b) => b.volume)
      .filter((v): v is number => v != null);
    if (vols.length) avgVol = vols.reduce((a, b) => a + b, 0) / vols.length;
    const highs = prices.ohlcv
      .map((b) => b.high)
      .filter((v): v is number => v != null);
    const lows = prices.ohlcv
      .map((b) => b.low)
      .filter((v): v is number => v != null);
    if (highs.length && lows.length) {
      range52 = `${vnd(Math.min(...lows))} – ${vnd(Math.max(...highs))}`;
    }
  }

  return [
    { label: "Giá", value: vnd(priceClose) },
    {
      label: "Vốn hoá",
      value: mcap != null ? `${num(mcap, 1)} tỷ` : "—",
    },
    {
      label: "KLGD TB 1 tháng",
      value: avgVol != null ? num(avgVol, 0) : "—",
    },
    { label: "Biên 52 tuần", value: range52 },
    {
      label: "SLCP",
      value: shares != null ? num(shares, 0) : "—",
    },
    { label: "Beta", value: beta != null ? num(beta, 2) : "—" },
  ];
}

function OverviewTab({
  symbol,
  profile,
  detail,
}: {
  symbol: string;
  profile: Profile;
  detail: TickerDetailResponse;
}) {
  const contrib = detail.result?.contributions || {
    F: null,
    T: null,
    V: null,
    S: null,
    R: null,
  };
  const queryClient = useQueryClient();
  const debateQ = useQuery({
    queryKey: ["debate", symbol, profile],
    queryFn: () => api.debate(symbol, profile, false),
  });
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobCreating, setJobCreating] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobRetryAfter, setJobRetryAfter] = useState<number | null>(null);
  const [countdown, setCountdown] = useState(120);
  const [liveResult, setLiveResult] = useState<DebateResponse | null>(null);
  const [clickedAi, setClickedAi] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const debate = liveResult || debateQ.data;
  const metaQ = useQuery({
    queryKey: ["meta"],
    queryFn: () => api.meta(),
  });
  const llmStatusQ = useQuery({
    queryKey: ["llm-status"],
    queryFn: () => api.llmStatus(),
  });
  const llm = llmStatusQ.data || metaQ.data?.llm;
  const llmState = String(llm?.state || (llm?.key_configured === false ? "no_key" : "ok"));
  const aiAttempt = (debate?.ai_attempt || {}) as {
    state?: string;
    reason_code?: string;
    retry_after?: number;
  };
  const isCreating = jobCreating || (!!jobId && !liveResult && !jobError);

  useEffect(() => {
    if (!isCreating) return;
    setCountdown(120);
    const t = setInterval(() => {
      setCountdown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(t);
  }, [isCreating, jobId]);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const st = await api.debateJobGet(symbol, jobId, profile);
        if (cancelled) return;
        if (st.state === "ok" || st.state === "failed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setJobCreating(false);
          if (st.state === "ok" && st.result) {
            setLiveResult(st.result);
            setJobError(null);
            queryClient.setQueryData(["debate", symbol, profile], st.result);
          } else {
            const code = String(st.reason_code || st.result?.reason || "llm_fallback_template");
            const ra =
              typeof st.retry_after === "number"
                ? st.retry_after
                : st.result?.ai_attempt?.retry_after ?? null;
            setJobRetryAfter(typeof ra === "number" ? ra : null);
            setJobError(viJobFailReason(code, typeof ra === "number" ? ra : undefined));
            if (st.result) {
              setLiveResult(st.result);
              queryClient.setQueryData(["debate", symbol, profile], st.result);
            }
          }
          setJobId(null);
        }
      } catch (e) {
        if (cancelled) return;
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setJobCreating(false);
        setJobId(null);
        setJobError(
          e instanceof ApiError && e.status === 429
            ? `Giới hạn tần suất — thử lại sau ${e.retryAfterSec ?? "…"} giây.`
            : "Không tải được trạng thái AI. Thử lại sau.",
        );
      }
    };
    void poll();
    pollRef.current = setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobId, symbol, profile, queryClient]);

  const startAiJob = async () => {
    setClickedAi(true);
    // Xóa ngay thông báo lỗi lần trước trước khi POST job mới
    setJobError(null);
    setJobRetryAfter(null);
    setLiveResult(null);
    setJobId(null);
    setJobCreating(true);
    setCountdown(120);
    try {
      const created = await api.debateJobCreate(symbol, profile);
      setJobId(created.job_id);
    } catch (e) {
      setJobCreating(false);
      if (e instanceof ApiError && e.status === 429) {
        setJobRetryAfter(e.retryAfterSec);
        setJobError(
          `Giới hạn tần suất — thử lại sau ${e.retryAfterSec ?? "…"} giây.`,
        );
      } else {
        setJobError("Không tạo được job AI. Thử lại sau.");
      }
    }
  };

  const sourceLabel = debateSourceLabel({
    isCreating,
    source: debate?.source,
    model: debate?.model || llm?.model,
    createdAt: debate?.created_at,
    asof: debate?.asof,
    formatWhen: dateVi,
  });

  const aiFailLine = debateFailLine({
    isCreating,
    jobError,
    clickedAi,
    aiAttemptState: aiAttempt.state,
    reasonCode: aiAttempt.reason_code,
    debateReason: debate?.reason,
    retryAfter: aiAttempt.retry_after ?? jobRetryAfter,
    viReason: viJobFailReason,
  });

  const blockedUntilLabel = useMemo(() => {
    const iso = llm?.blocked_until;
    if (!iso || typeof iso !== "string") {
      return llm?.blocked_until_local || null;
    }
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return String(iso);
      // Asia/Ho_Chi_Minh
      const fmt = new Intl.DateTimeFormat("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
      });
      const parts = fmt.formatToParts(d);
      const get = (t: string) => parts.find((p) => p.type === t)?.value || "";
      return `${get("hour")}:${get("minute")} ${get("day")}/${get("month")}`;
    } catch {
      return String(iso);
    }
  }, [llm?.blocked_until, llm?.blocked_until_local]);

  const pricesQ = useQuery({
    queryKey: ["prices-overview", symbol, profile],
    queryFn: () =>
      api.prices(symbol, {
        range: "1y",
        profile,
        include_index: true,
        include_indicators: true,
      }),
  });
  const checksQ = useQuery({
    queryKey: ["checks", symbol, profile],
    queryFn: () => api.checks(symbol, profile),
  });
  const quarterQ = useQuery({
    queryKey: ["quarter-summary", symbol],
    queryFn: () => api.quarterSummary(symbol),
  });
  const peersQ = useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => api.peers(symbol),
  });
  const sectorsQ = useQuery({
    queryKey: ["sectors", profile],
    queryFn: () => api.sectors(profile),
  });

  const riskOpp = useMemo(() => buildRiskOpportunity(detail), [detail]);
  const sectorMedianScores = useMemo(() => {
    const sec = detail.company?.sector;
    if (!sec) return null;
    const hit = (sectorsQ.data?.items || []).find((s) => s.sector === sec);
    return hit?.mean_pillars ?? null;
  }, [detail.company?.sector, sectorsQ.data]);

  const [showFailed, setShowFailed] = useState(false);
  const fScore = checksQ.data?.f_score;
  const tip = checksQ.data?.basis_tooltip || {};

  return (
    <section>
      <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>Giá 1 năm</h2>
      {pricesQ.isLoading && <div className="skeleton" />}
      {pricesQ.isError && (
        <div className="error-box">
          Không tải được giá. Kiểm tra kết nối API rồi tải lại trang.
        </div>
      )}
      {pricesQ.data && <OverviewPriceChart data={pricesQ.data} />}

      <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600, marginTop: 24 }}>
        Điểm đến từ đâu
      </h2>
      <p className="muted" style={{ marginTop: 0, fontSize: "var(--fs-sm)", maxWidth: "70ch" }}>
        Mỗi thành phần cộng (hoặc trừ) vào điểm tổng — không phải xếp hạng riêng.
      </p>
      <ContributionBars contrib={contrib} />

      {detail.pillar_rank && (
        <div className="pillar-ranks" style={{ marginTop: 20 }}>
          <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>
            Xếp hạng trong ngành
          </h2>
          {(
            [
              ["V", "Định giá"],
              ["F", "Cơ bản"],
              ["T", "Kỹ thuật"],
              ["S", "Tin tức"],
              ["safety", "An toàn"],
            ] as const
          ).map(([k, lab]) => {
            const pr = detail.pillar_rank?.[k];
            if (!pr || pr.top_pct == null) return null;
            return (
              <div className="pillar-rank-row" key={k}>
                <span>
                  {lab}: top {pr.top_pct}% ngành ({pr.n} mã)
                </span>
                <div className="pct-bar" aria-hidden>
                  <i style={{ width: `${Math.max(2, 100 - (pr.top_pct || 0))}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="radar-block" style={{ marginTop: 20 }}>
        <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>Radar thành phần</h2>
        <PillarRadar scores={detail.result?.scores} sectorMedian={sectorMedianScores} />
      </div>

      <div className="checks-block" style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>
          Điểm mạnh / yếu
          {fScore && !fScore.hide && fScore.label ? (
            <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
              {fScore.label}
            </span>
          ) : null}
        </h2>
        <div className="risk-opp-grid">
          <section>
            <h3 className="pos" style={{ fontSize: "var(--fs-sm)", margin: "0 0 6px" }}>
              ★ Cơ hội {checksQ.data ? checksQ.data.rewards_count : "…"}
            </h3>
            <CheckTable
              items={checksQ.data?.rewards || []}
              tip={tip}
              empty="Chưa có điểm nổi bật."
            />
          </section>
          <section>
            <h3 className="neg" style={{ fontSize: "var(--fs-sm)", margin: "0 0 6px" }}>
              ▲ Rủi ro {checksQ.data ? checksQ.data.risks_count : "…"}
            </h3>
            <CheckTable
              items={checksQ.data?.risks || []}
              tip={tip}
              empty="Chưa có điểm nổi bật."
            />
          </section>
        </div>
        {((checksQ.data?.cleared_risks?.length ||
          checksQ.data?.risks_failed?.length ||
          0) > 0) && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: "var(--fs-sm)", margin: "0 0 6px" }}>
              Đã kiểm, không có vấn đề (
              {(checksQ.data?.cleared_risks || checksQ.data?.risks_failed || []).length})
            </h3>
            <CheckTable
              items={checksQ.data?.cleared_risks || checksQ.data?.risks_failed || []}
              tip={tip}
              empty=""
            />
          </div>
        )}
        {((checksQ.data?.not_met?.length || 0) > 0) && (
          <details
            open={showFailed}
            onToggle={(e) => setShowFailed((e.target as HTMLDetailsElement).open)}
          >
            <summary className="muted">
              Chưa đạt ({(checksQ.data?.not_met || []).length})
            </summary>
            <CheckTable items={checksQ.data?.not_met || []} tip={tip} empty="" muted />
          </details>
        )}
      </div>

      {quarterQ.data?.available && (
        <div className="quarter-block" style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>
            Quý gần nhất {quarterQ.data.period}
          </h2>
          <ul className="prose" style={{ marginTop: 4 }}>
            {Object.entries(quarterQ.data.items || {}).map(([k, v]) => {
              if (v.value == null) return null;
              const lab =
                k === "revenue"
                  ? "Doanh thu"
                  : k === "gross_profit"
                    ? "Lãi gộp"
                    : k === "net_income" || k === "net_income_parent"
                      ? "LNST"
                      : k;
              return (
                <li key={k}>
                  {lab}: {compactBillions((v.value || 0) / 1e9)}
                  {v.yoy != null ? ` (YoY ${pct(v.yoy)})` : ""}
                </li>
              );
            })}
          </ul>
          {quarterQ.data.price_reaction &&
            quarterQ.data.price_reaction.return_1d != null && (
              <p className="prose">
                Sau ngày công bố, giá thay đổi{" "}
                {pct(quarterQ.data.price_reaction.return_1d)} trong 1 phiên
                {quarterQ.data.price_reaction.return_5d != null
                  ? `, ${pct(quarterQ.data.price_reaction.return_5d)} sau 5 phiên`
                  : ""}
                .
              </p>
            )}
        </div>
      )}

      <div className="risk-opp" style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>
          Gợi ý nhanh từ điểm số
        </h2>
        <div className="risk-opp-grid">
          <section>
            <h3 className="pos" style={{ fontSize: "var(--fs-sm)", margin: "0 0 6px" }}>
              Cơ hội
            </h3>
            <ul className="prose" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {riskOpp.opportunities.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="neg" style={{ fontSize: "var(--fs-sm)", margin: "0 0 6px" }}>
              Rủi ro
            </h3>
            <ul className="prose" style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {riskOpp.risks.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      {peersQ.data?.items && peersQ.data.items.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600 }}>
            Đồng ngành (vốn hoá)
          </h2>
          <ul className="peer-mcap-list">
            {peersQ.data.items
              .filter((p) => !p.is_self)
              .slice(0, 6)
              .map((p) => (
                <li key={p.ticker}>
                  <Link to={`/t/${p.ticker}?profile=${profile}`}>{p.ticker}</Link>
                  <span className="muted tabular">
                    {" "}
                    {p.market_cap != null
                      ? `${num(p.market_cap / 1e9, 1)} tỷ`
                      : "—"}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}

      <h2 style={{ fontSize: "var(--fs-md)", fontWeight: 600, marginTop: 24 }}>
        Luận điểm thuận / nghịch
      </h2>
      <div style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="badge" data-testid="debate-source-label">
          Nguồn: {sourceLabel}
        </span>
        {llmState === "no_key" && (
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
            Chưa cấu hình AI
          </span>
        )}
        {llmState === "quota_blocked" && (
          <>
            <button type="button" disabled>
              Tạo lại bằng AI
            </button>
            <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
              Hết hạn mức AI, dùng lại được từ {blockedUntilLabel || "…"}
            </span>
          </>
        )}
        {llmState === "circuit_open" && (
          <>
            <button type="button" disabled>
              Tạo lại bằng AI
            </button>
            <span className="muted" style={{ fontSize: "var(--fs-xs)" }} data-testid="circuit-retry">
              AI tạm nghỉ do lỗi liên tiếp
              {typeof llm?.retry_after === "number"
                ? ` — thử lại sau khoảng ${llm.retry_after} giây`
                : ""}
            </span>
          </>
        )}
        {llmState === "ok" && (
          <>
            <button
              type="button"
              onClick={() => void startAiJob()}
              disabled={isCreating || (jobRetryAfter != null && jobRetryAfter > 0)}
              data-testid="debate-ai-btn"
            >
              {isCreating ? "Đang tạo…" : "Tạo lại bằng AI"}
            </button>
            {isCreating && (
              <span className="muted tabular" style={{ fontSize: "var(--fs-xs)" }}>
                Còn khoảng {countdown} giây
              </span>
            )}
            {!isCreating && !aiFailLine && (
              <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                Dùng lượt gọi AI, có giới hạn
                {typeof debate?.quota_remaining === "number"
                  ? ` — còn ${debate.quota_remaining} lượt/giờ`
                  : ""}
              </span>
            )}
          </>
        )}
      </div>
      {aiFailLine && (
        <p
          className="muted"
          style={{ fontSize: "var(--fs-xs)", margin: "0 0 8px" }}
          role="status"
          data-testid="debate-fail-line"
        >
          {aiFailLine}
          {!isCreating && llmState === "ok" && (
            <>
              {" "}
              <button
                type="button"
                onClick={() => {
                  if (jobRetryAfter && jobRetryAfter > 0) return;
                  void startAiJob();
                }}
                disabled={!!(jobRetryAfter && jobRetryAfter > 0)}
                data-testid="debate-retry-btn"
              >
                Thử lại
              </button>
            </>
          )}
        </p>
      )}
      {debateQ.isError && !debate && (
        <div className="error-box" role="alert">
          {(debateQ.error as ApiError)?.status === 429
            ? `Giới hạn tần suất — thử lại sau ${
                (debateQ.error as ApiError).retryAfterSec ?? "…"
              } giây.`
            : "Không tải được luận điểm. Thử «Tạo lại bằng AI» hoặc đợi rồi tải lại."}
        </div>
      )}
      {debateQ.isLoading && !debate && <div className="skeleton" />}
      {debate && (
        <div className="debate-panel">
          <section>
            <h3 className="pos">Thuận</h3>
            <ul>
              {cleanDebateItems(debate.bull).map((b, i) => (
                <li key={i}>{b.text}</li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="neg">Nghịch</h3>
            <ul>
              {cleanDebateItems(debate.bear).map((b, i) => (
                <li key={i}>{b.text}</li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </section>
  );
}

function FinancialsTab({
  symbol,
  isBank,
  mode = "growth",
}: {
  symbol: string;
  isBank?: boolean;
  mode?: "growth" | "health" | "dividend";
}) {
  const q = useQuery({
    queryKey: ["financials", symbol],
    queryFn: () => api.financials(symbol),
  });
  if (q.isLoading) return <div className="skeleton" />;
  if (q.isError)
    return (
      <div className="error-box">
        Không tải được báo cáo tài chính. Tải lại trang hoặc chọn mã khác.
      </div>
    );
  const data = q.data!;
  const latestYear = data.annual.length
    ? data.annual[data.annual.length - 1]
    : null;
  const last4q = data.quarterly.slice(-4);
  const yearBridge =
    !isBank && latestYear && mode === "growth"
      ? buildIncomeBridge(latestYear.items)
      : null;
  const ttmItems =
    !isBank && last4q.length === 4 && mode === "growth"
      ? sumPeriodItems(last4q, [
          "revenue",
          "gross_profit",
          "selling_expense",
          "admin_expense",
          "ebit",
          "interest_expense",
          "pretax_profit",
          "net_income",
          "net_income_parent",
          "dividends_paid",
        ])
      : null;
  const ttmBridge = ttmItems ? buildIncomeBridge(ttmItems) : null;

  if (mode === "dividend") {
    // Tab trống: chỉ thông báo — không kèm chú thích đơn vị/ROE
    return (
      <section>
        <DividendPanel rows={data.annual} />
      </section>
    );
  }

  return (
    <section>
      {mode === "growth" && (
        <IncomeFlowPanel symbol={symbol} isBank={isBank} />
      )}
      <p className="muted" style={{ fontSize: "var(--fs-xs)", maxWidth: "70ch" }}>
        {FIN_UNIT_ROE_NOTE}
      </p>
      {mode === "growth" && !isBank && (yearBridge || ttmBridge) && (
        <div className="waterfall-block">
          <h3>Từ doanh thu đến lợi nhuận (cầu)</h3>
          {yearBridge && (
            <>
              <p className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                Năm {String(latestYear?.period)} (tỷ đồng)
              </p>
              <WaterfallChart bridge={yearBridge} />
            </>
          )}
          {ttmBridge && (
            <>
              <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 16 }}>
                4 quý gần nhất (TTM, tỷ đồng)
              </p>
              <WaterfallChart bridge={ttmBridge} />
            </>
          )}
        </div>
      )}
      {mode === "growth" && (
        <>
          <h3>Quý</h3>
          <QuarterlyFinCharts rows={data.quarterly} />
          <FinTable rows={data.quarterly} mode="quarterly" />
        </>
      )}
      {mode === "health" && (
        <>
          <h3 style={{ marginTop: 8 }}>Năm</h3>
          <AnnualFinCharts rows={data.annual} />
          <FinTable rows={data.annual} mode="annual" />
        </>
      )}
    </section>
  );
}

function WaterfallChart({
  bridge,
}: {
  bridge: NonNullable<ReturnType<typeof buildIncomeBridge>>;
}) {
  const vals = bridge.steps.map((s) => s.value);
  const maxAbs = Math.max(...vals.map((v) => Math.abs(v)), 1);
  return (
    <div className="waterfall" role="img" aria-label="Cầu doanh thu đến lợi nhuận">
      {bridge.steps.map((s, i) => {
        const h = (Math.abs(s.value) / maxAbs) * 100;
        const neg = s.value < 0;
        return (
          <div className="wf-col" key={`${s.label}-${i}`}>
            <div className="wf-val tabular">{num(s.value, 1)}</div>
            <div className="wf-track">
              <div
                className={`wf-bar ${s.kind === "absolute" ? "wf-abs" : neg ? "wf-neg" : "wf-pos"}`}
                style={{ height: `${Math.max(4, h)}%` }}
              />
            </div>
            <div className="wf-lab">{s.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function FinTable({
  rows,
  mode,
}: {
  rows: import("../api/types").FinancialPeriod[];
  mode: "annual" | "quarterly";
}) {
  if (!rows.length)
    return (
      <div className="empty">
        Chưa có dữ liệu. Đợi snapshot cập nhật hoặc chọn mã khác.
      </div>
    );
  return (
    <div style={{ overflowX: "auto", marginTop: 12 }}>
      <table className="fin-table tabular">
        <thead>
          <tr>
            <th>Chỉ tiêu (tỷ đồng)</th>
            {rows.map((r) => (
              <th key={String(r.period)}>{r.period}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Doanh thu</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{compactBillions(r.items.revenue ?? null)}</td>
            ))}
          </tr>
          <tr>
            <td>LNST</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{compactBillions(r.items.net_income ?? null)}</td>
            ))}
          </tr>
          <tr>
            <td>Biên gộp</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{pct(r.gross_margin)}</td>
            ))}
          </tr>
          <tr>
            <td>ROE</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{pct(r.roe)}</td>
            ))}
          </tr>
          <tr>
            <td>Nợ/VCSH</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{num(r.debt_to_equity, 2)}</td>
            ))}
          </tr>
          <tr>
            <td>CFO</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{compactBillions(r.items.cfo ?? null)}</td>
            ))}
          </tr>
          <tr>
            <td>Capex</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{compactBillions(r.items.capex ?? null)}</td>
            ))}
          </tr>
          <tr>
            <td>FCF</td>
            {rows.map((r) => (
              <td key={String(r.period)}>{compactBillions(r.fcf)}</td>
            ))}
          </tr>
          {mode === "annual" && (
            <>
              <tr>
                <td>DT YoY</td>
                {rows.map((r) => (
                  <td key={String(r.period)}>{pct(r.revenue_yoy ?? null)}</td>
                ))}
              </tr>
              <tr>
                <td>LNST YoY</td>
                {rows.map((r) => (
                  <td key={String(r.period)}>{pct(r.net_income_yoy ?? null)}</td>
                ))}
              </tr>
            </>
          )}
          {mode === "quarterly" && (
            <tr>
              <td>DT QoQ</td>
              {rows.map((r) => (
                <td key={String(r.period)}>{pct(r.revenue_qoq ?? null)}</td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ValuationTab({
  symbol,
  profile,
  detail,
  priceClose,
  refDisplay,
}: {
  symbol: string;
  profile: Profile;
  detail: TickerDetailResponse;
  priceClose: number | null;
  refDisplay: number | null;
}) {
  const q = useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => api.peers(symbol),
  });
  const statsQ = useQuery({
    queryKey: ["snapshot-stats", symbol, profile],
    queryFn: () => api.snapshotStats(symbol, profile),
  });
  const pricesQ = useQuery({
    queryKey: ["prices-val", symbol],
    queryFn: () =>
      api.prices(symbol, { range: "1y", include_indicators: false }),
  });

  const isBank = !!(detail.company as { is_bank?: boolean } | null)?.is_bank
    || String(detail.company?.sector || "").toLowerCase().includes("bank");

  const low52 = useMemo(() => {
    const lows = (pricesQ.data?.ohlcv || [])
      .map((b) => b.low)
      .filter((v): v is number => v != null);
    return lows.length ? Math.min(...lows) : null;
  }, [pricesQ.data]);
  const high52 = useMemo(() => {
    const highs = (pricesQ.data?.ohlcv || [])
      .map((b) => b.high)
      .filter((v): v is number => v != null);
    return highs.length ? Math.max(...highs) : null;
  }, [pricesQ.data]);

  if (q.isLoading) return <div className="skeleton" />;
  if (q.isError)
    return (
      <div className="error-box">
        Không tải được peers. Tải lại trang hoặc thử mã khác.
      </div>
    );
  const data = q.data!;
  const self = data.items.find((p) => p.is_self);

  return (
    <section>
      <p className="muted" style={{ maxWidth: "70ch" }}>
        Trung vị ngành {sectorVi(data.sector_medians.sector || data.sector)}
        <br />
        P/E {num(data.sector_medians.median_pe ?? null, 1)}
        <span style={{ margin: "0 10px", color: "var(--rule)" }} aria-hidden>
          |
        </span>
        P/B {num(data.sector_medians.median_pb ?? null, 2)}
      </p>
      {statsQ.data?.items && (
        <div className="stats-grid" aria-label="Chỉ số định giá nhanh">
          {statsQ.data.items.map((it) => (
            <div className={`stat-cell tone-${it.tone || "neutral"}`} key={it.id}>
              <span className="stat-lab">
                <i className="tone-mark" aria-hidden />
                {it.label_vi}
              </span>
              <strong className="tabular">
                {it.value == null
                  ? "—"
                  : it.unit === "%"
                    ? pct(
                        Math.abs(it.value) > 1.5 ? it.value / 100 : it.value,
                      )
                    : it.unit === "VND" || it.unit === "cp"
                      ? num(it.value, 0)
                      : num(it.value, 2)}
              </strong>
            </div>
          ))}
        </div>
      )}
      <ValuationCharts
        isBank={isBank}
        peers={data.items}
        peBand={data.sector_medians.pe_band}
        pbBand={data.sector_medians.pb_band}
        ownPe={self?.pe ?? null}
        ownPb={self?.pb ?? null}
        price={priceClose}
        refPrice={refDisplay}
        low52={low52}
        high52={high52}
      />
      <table className="fin-table tabular" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>Mã</th>
            {!isBank && <th>P/E</th>}
            <th>P/B</th>
            <th>ROE</th>
            <th>Vốn hoá</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((p) => (
            <tr key={p.ticker} style={p.is_self ? { fontWeight: 600 } : undefined}>
              <td style={{ textAlign: "left" }}>
                {p.ticker}
                {p.is_self ? " (mã này)" : ""}
              </td>
              {!isBank && <td>{num(p.pe, 1)}</td>}
              <td>{num(p.pb, 2)}</td>
              <td>{pct(p.roe)}</td>
              <td>{p.market_cap != null ? compactBillions(p.market_cap / 1e9) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 12, maxWidth: "70ch" }}>
        Giá tham chiếu theo ngành suy ra từ bội số trung vị ngành (P/E, P/B), không phải dự
        báo giá mục tiêu. Không dùng chênh lệch như mức tăng kỳ vọng.
      </p>
    </section>
  );
}

function TechnicalTab({ symbol, profile }: { symbol: string; profile: Profile }) {
  const [range, setRange] = useState("6m");
  const q = useQuery({
    queryKey: ["prices", symbol, range, profile],
    queryFn: () =>
      api.prices(symbol, {
        range,
        profile,
        include_index: true,
        include_indicators: true,
      }),
  });

  const idxRebased = useMemo(() => {
    const series = q.data?.index?.series;
    if (!series?.length) return null;
    const first = series.find((p) => p.close != null && p.close > 0);
    if (!first?.close) return null;
    const base = first.close;
    return series
      .filter((p) => p.close != null)
      .map((p) => ({ time: p.time, value: (Number(p.close) / base) * 100 }));
  }, [q.data]);

  return (
    <section>
      <label>
        Khoảng{" "}
        <select value={range} onChange={(e) => setRange(e.target.value)} aria-label="Khoảng thời gian">
          <option value="3m">3 tháng</option>
          <option value="6m">6 tháng</option>
          <option value="1y">1 năm</option>
          <option value="all">Toàn bộ</option>
        </select>
      </label>
      {q.isLoading && <div className="skeleton" />}
      {q.isError && (
        <div className="error-box">
          Không tải được giá. Kiểm tra API rồi tải lại.
        </div>
      )}
      {q.data && <TechnicalChart data={q.data} />}
      {idxRebased && <IndexRebasedMini points={idxRebased} />}
      {q.data?.index?.series == null && q.data?.index?.note && (
        <p className="muted">{q.data.index.note}</p>
      )}
    </section>
  );
}

function IndexRebasedMini({
  points,
}: {
  points: Array<{ time: string; value: number }>;
}) {
  const w = 640;
  const h = 80;
  const vals = points.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const poly = points
    .map((p, i) => {
      const x = (i / Math.max(1, points.length - 1)) * (w - 8) + 4;
      const y = h - 8 - ((p.value - min) / span) * (h - 16);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div className="fin-chart-block" style={{ marginTop: 12 }}>
      <h4 className="fin-chart-title">VN-Index (gốc 100)</h4>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" className="fin-spark" role="img" aria-label="VN-Index rebased">
        <polyline fill="none" stroke="var(--ink-2)" strokeWidth="2" points={poly} />
      </svg>
    </div>
  );
}

function NewsTab({ symbol, profile }: { symbol: string; profile: Profile }) {
  const q = useQuery({
    queryKey: ["news", symbol, profile],
    queryFn: () => api.news(symbol, profile),
  });
  if (q.isLoading) return <div className="skeleton" />;
  if (q.isError)
    return (
      <div className="error-box">
        Không tải được tin. Tải lại trang hoặc thử sau.
      </div>
    );
  const items = q.data?.items || [];
  if (!items.length)
    return (
      <div className="empty">
        Chưa có tin đã phân loại. Đợi snapshot tin cập nhật hoặc chọn mã khác.
      </div>
    );
  return (
    <ul style={{ paddingLeft: 0, listStyle: "none" }}>
      {items.map((n) => (
        <li
          key={n.id}
          style={{
            borderBottom: "1px solid var(--rule)",
            padding: "10px 0",
          }}
        >
          <div>
            {n.url ? (
              <a href={n.url} target="_blank" rel="noreferrer">
                {n.title}
              </a>
            ) : (
              n.title
            )}
          </div>
          <div
            className="muted"
            style={{
              fontSize: "var(--fs-xs)",
              display: "flex",
              flexWrap: "wrap",
              gap: "4px 12px",
            }}
          >
            <span>{n.label}</span>
            <span>{n.source || "—"}</span>
            <span className="tabular">{dateVi(n.published_at)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

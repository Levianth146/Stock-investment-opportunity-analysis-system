import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile, RankingRow } from "../api/types";
import { PillarBars, ratingClass } from "../components/PillarBars";
import { ScoreRuler } from "../components/ScoreRuler";
import {
  type SignalFilter,
  useRankingsUrlState,
} from "../hooks/useUrlState";
import { num, score, vnd } from "../fmt";
import { ratingsFromMeta } from "../ratings";
import { sectorVi } from "../sectors";

const SIGNAL_CHIPS: { id: SignalFilter; label: string }[] = [
  { id: "above_ma50", label: "Trên MA50" },
  { id: "above_ma200", label: "Trên MA200" },
  { id: "rsi_ob", label: "RSI > 70 (quá mua)" },
  { id: "rsi_os", label: "RSI < 30 (quá bán)" },
  { id: "vol_up", label: "Khối lượng tăng" },
  { id: "low_risk", label: "Ít rủi ro (≤ 1)" },
];

function passesSignals(row: RankingRow, filters: Set<SignalFilter>): boolean {
  if (!filters.size) return true;
  const s = row.signals;
  if (!s) return false;
  for (const f of filters) {
    if (f === "above_ma50" && s.above_ma50 !== true) return false;
    if (f === "above_ma200" && s.above_ma200 !== true) return false;
    if (f === "rsi_ob" && s.rsi_zone !== "overbought") return false;
    if (f === "rsi_os" && s.rsi_zone !== "oversold") return false;
    if (f === "vol_up" && s.volume_up !== true) return false;
    if (f === "low_risk" && !(typeof row.risks_count === "number" && row.risks_count <= 1))
      return false;
  }
  return true;
}

export function RankingsPage() {
  const { state, patch } = useRankingsUrlState();

  const metaQ = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const ratings = ratingsFromMeta(metaQ.data);

  const sectorsQ = useQuery({
    queryKey: ["sectors", state.profile],
    queryFn: () => api.sectors(state.profile),
  });

  /** Toàn bộ mã có điểm theo profile — rug + highlight khi lọc. */
  const allScoredQ = useQuery({
    queryKey: ["rankings-all", state.profile],
    queryFn: () =>
      api.rankings({
        profile: state.profile,
        limit: 500,
        offset: 0,
        include_unranked: false,
      }),
  });

  const rankedQ = useQuery({
    queryKey: ["rankings", state.profile, state.sector, state.q, state.sort, state.order],
    queryFn: () =>
      api.rankings({
        profile: state.profile,
        sector: state.sector || undefined,
        q: state.q || undefined,
        sort: state.sort,
        order: state.order,
        limit: 500,
        offset: 0,
        include_unranked: false,
      }),
  });

  const unrankedQ = useQuery({
    queryKey: ["rankings-unranked", state.profile, state.sector, state.q],
    queryFn: () =>
      api.rankings({
        profile: state.profile,
        sector: state.sector || undefined,
        q: state.q || undefined,
        limit: 1000,
        include_unranked: true,
      }),
  });

  const ranked = useMemo(() => {
    const items = rankedQ.data?.items ?? [];
    if (!state.signals.size) return items;
    return items.filter((r) => passesSignals(r, state.signals));
  }, [rankedQ.data, state.signals]);
  const allScores = useMemo(
    () =>
      (allScoredQ.data?.items ?? [])
        .map((r) => r.score)
        .filter((s): s is number => typeof s === "number"),
    [allScoredQ.data],
  );
  const filteredScores = useMemo(
    () => ranked.map((r) => r.score).filter((s): s is number => typeof s === "number"),
    [ranked],
  );
  const filtering = !!(state.sector || state.q || state.signals.size);

  const toggleSignal = (id: SignalFilter) => {
    const next = new Set(state.signals);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    patch({ signals: next });
  };

  const unranked = useMemo(() => {
    const all = unrankedQ.data?.items ?? [];
    return all.filter((r) => !r.ranked);
  }, [unrankedQ.data]);

  const [unrankedReason, setUnrankedReason] = useState<string | null>(null);
  const [unrankedQstr, setUnrankedQstr] = useState("");
  const [unrankedPage, setUnrankedPage] = useState(0);

  const unrankedByReason = useMemo(() => {
    const map = new Map<string, RankingRow[]>();
    for (const r of unranked) {
      const reasons = r.quality_gate?.reasons || [];
      const keys = reasons.length ? reasons : ["Thiếu dữ liệu để chấm điểm"];
      for (const k of keys) {
        const list = map.get(k) || [];
        list.push(r);
        map.set(k, list);
      }
    }
    return [...map.entries()]
      .map(([reason, rows]) => ({ reason, count: rows.length, rows }))
      .sort((a, b) => b.count - a.count);
  }, [unranked]);

  const unrankedDetail = useMemo(() => {
    if (!unrankedReason) return [];
    const hit = unrankedByReason.find((x) => x.reason === unrankedReason);
    let rows = hit?.rows || [];
    const q = unrankedQstr.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) =>
          r.ticker.toLowerCase().includes(q) ||
          (r.name || "").toLowerCase().includes(q),
      );
    }
    return rows;
  }, [unrankedReason, unrankedByReason, unrankedQstr]);

  const unrankedPageSize = 50;
  const unrankedPages = Math.max(1, Math.ceil(unrankedDetail.length / unrankedPageSize));
  const unrankedSlice = unrankedDetail.slice(
    unrankedPage * unrankedPageSize,
    (unrankedPage + 1) * unrankedPageSize,
  );

  const selectedSectorLabel = useMemo(() => {
    if (!state.sector) return null;
    const hit = (sectorsQ.data?.items || []).find((s) => s.sector === state.sector);
    return sectorVi(hit?.label || state.sector);
  }, [state.sector, sectorsQ.data]);

  const onSort = (key: string) => {
    if (state.sort === key) {
      patch({ order: state.order === "desc" ? "asc" : "desc" });
    } else {
      patch({ sort: key, order: "desc" });
    }
  };

  return (
    <main>
      <h1 style={{ margin: "0 0 8px", fontSize: "var(--fs-lg)", fontWeight: 600 }}>
        Bảng xếp hạng
      </h1>
      <p className="muted prose" style={{ marginTop: 0, fontFamily: "var(--font)" }}>
        Chấm điểm {metaQ.data?.scored_count ?? "…"}/{metaQ.data?.universe_count ?? "…"} mã
        {unranked.length > 0 ? `; ${unranked.length} mã thiếu dữ liệu` : ""}. Giá tham chiếu
        theo ngành chỉ xem trên trang mã.
      </p>

      <div className="toolbar">
        <label>
          <span className="muted">Tìm </span>
          <input
            type="search"
            placeholder="Mã hoặc tên"
            value={state.q}
            onChange={(e) => patch({ q: e.target.value })}
            aria-label="Tìm mã"
          />
        </label>
        <label>
          <span className="muted">Ngành </span>
          <select
            value={state.sector}
            onChange={(e) => patch({ sector: e.target.value })}
            aria-label="Lọc ngành"
          >
            <option value="">Tất cả</option>
            {(sectorsQ.data?.items || []).map((s) => (
              <option key={s.sector} value={s.sector}>
                {sectorVi(s.label || s.sector)} ({s.n_scored ?? s.count})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="muted">Kiểu đầu tư </span>
          <select
            value={state.profile}
            onChange={(e) => patch({ profile: e.target.value as Profile })}
            aria-label="Kiểu đầu tư"
          >
            <option value="long_term">Dài hạn</option>
            <option value="swing">Lướt sóng</option>
          </select>
        </label>
      </div>

      {selectedSectorLabel && (
        <div className="sector-chip" aria-label={`Đang lọc ngành ${selectedSectorLabel}`}>
          {selectedSectorLabel}
        </div>
      )}

      <div className="signal-chips" role="group" aria-label="Lọc tín hiệu kỹ thuật">
        {SIGNAL_CHIPS.map((c) => {
          const on = state.signals.has(c.id);
          return (
            <button
              key={c.id}
              type="button"
              className={on ? "signal-chip signal-chip--on" : "signal-chip"}
              aria-pressed={on}
              onClick={() => toggleSignal(c.id)}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {rankedQ.isLoading && <div className="skeleton" aria-busy="true" />}
      {rankedQ.isError && (
        <div className="error-box" role="alert">
          Không tải được bảng xếp hạng. Kiểm tra API đang chạy rồi tải lại trang.
        </div>
      )}

      <HomeMarketPanel ratings={ratings} allScores={allScores} />

      {allScores.length > 0 && (
        <ScoreRuler
          ratings={ratings}
          rug={allScores}
          rugHighlight={filtering ? filteredScores : undefined}
          aria-label="Phân bố điểm theo profile"
        />
      )}

      <div className="pillars-legend" aria-label="Thứ tự thành phần điểm">
        {["Cơ bản", "Kỹ thuật", "Định giá", "Tin tức", "Rủi ro"].map((lab) => (
          <span className="pl-item" key={lab}>
            <i className="pl-swatch" aria-hidden />
            {lab}
          </span>
        ))}
      </div>

      <div className="table-wrap rankings-table" role="table" aria-label="Bảng xếp hạng">
        <div className="rank-head" role="row">
          <span>Mã</span>
          <span>Tên</span>
          <span>Ngành</span>
          <button
            type="button"
            className="sort-btn"
            onClick={() => onSort("score")}
            aria-sort={
              state.sort === "score"
                ? state.order === "desc"
                  ? "descending"
                  : "ascending"
                : "none"
            }
          >
            Điểm
          </button>
          <span>Thước</span>
          <span>Khuyến nghị</span>
          <span className="rank-head-pillars" aria-hidden>
            {" "}
          </span>
          <span>Giá</span>
          <span title="Số phép kiểm cơ hội đạt">Cơ hội</span>
          <span title="Số phép kiểm rủi ro đạt">Rủi ro</span>
        </div>

        {ranked.length === 0 && !rankedQ.isLoading && (
          <div className="empty">
            Không có mã phù hợp bộ lọc. Xóa từ khóa hoặc chọn «Tất cả» ngành.
          </div>
        )}

        {ranked.map((row) => (
          <div key={row.ticker} className="rank-row" role="row">
            <RankCells row={row} profile={state.profile} ratings={ratings} />
          </div>
        ))}
      </div>

      <details className="unranked-block">
        <summary>Không xếp hạng ({unranked.length})</summary>
        {unranked.length === 0 ? (
          <p className="muted">Không có mã ngoài bảng xếp hạng.</p>
        ) : (
          <div className="unranked-reasons">
            <p className="muted" style={{ fontSize: "var(--fs-sm)" }}>
              Tóm tắt theo lý do (một mã có thể thuộc nhiều lý do):
            </p>
            <table className="check-table">
              <thead>
                <tr>
                  <th scope="col">Lý do</th>
                  <th scope="col">Số mã</th>
                </tr>
              </thead>
              <tbody>
                {unrankedByReason.map((row) => (
                  <tr key={row.reason}>
                    <td>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => {
                          setUnrankedReason(row.reason);
                          setUnrankedPage(0);
                          setUnrankedQstr("");
                        }}
                      >
                        {row.reason}
                      </button>
                    </td>
                    <td className="tabular">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {unrankedReason && (
              <div className="unranked-detail" style={{ marginTop: 16 }}>
                <h3 style={{ fontSize: "var(--fs-sm)", margin: "0 0 8px" }}>
                  {unrankedReason} ({unrankedDetail.length})
                </h3>
                <label>
                  <span className="muted">Tìm </span>
                  <input
                    type="search"
                    value={unrankedQstr}
                    onChange={(e) => {
                      setUnrankedQstr(e.target.value);
                      setUnrankedPage(0);
                    }}
                    aria-label="Tìm mã không xếp hạng"
                  />
                </label>
                <table className="check-table" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th scope="col">Mã</th>
                      <th scope="col">Tên</th>
                      <th scope="col">Ngành</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unrankedSlice.map((r) => (
                      <tr key={r.ticker}>
                        <td>
                          <Link to={`/t/${r.ticker}?profile=${state.profile}`}>
                            {r.ticker}
                          </Link>
                        </td>
                        <td>{r.name || "—"}</td>
                        <td className="muted">{sectorVi(r.sector || "")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {unrankedPages > 1 && (
                  <div className="pager" style={{ marginTop: 8, display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      disabled={unrankedPage <= 0}
                      onClick={() => setUnrankedPage((p) => Math.max(0, p - 1))}
                    >
                      Trước
                    </button>
                    <span className="muted tabular">
                      {unrankedPage + 1}/{unrankedPages}
                    </span>
                    <button
                      type="button"
                      disabled={unrankedPage + 1 >= unrankedPages}
                      onClick={() =>
                        setUnrankedPage((p) => Math.min(unrankedPages - 1, p + 1))
                      }
                    >
                      Sau
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </details>
    </main>
  );
}

function HomeMarketPanel({
  ratings,
  allScores,
}: {
  ratings: ReturnType<typeof ratingsFromMeta>;
  allScores: number[];
}) {
  const [period, setPeriod] = useState<"1m" | "3m" | "1y">("1m");
  const marketQ = useQuery({
    queryKey: ["market"],
    queryFn: () => api.market(),
    staleTime: 300_000,
  });
  const series = marketQ.data?.index?.series_30d || [];
  const breadth = useMemo(() => {
    const dist: Record<string, number> = {};
    // Ước từ ratings thresholds + allScores
    for (const sc of allScores) {
      let lab = ratings[0]?.label || "—";
      for (let i = ratings.length - 1; i >= 0; i--) {
        const r = ratings[i]!;
        if (sc >= r.min) {
          lab = r.label;
          break;
        }
      }
      dist[lab] = (dist[lab] || 0) + 1;
    }
    return dist;
  }, [allScores, ratings]);
  const total = Object.values(breadth).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="home-market" aria-label="Thị trường">
      <div className="home-market-head">
        <strong>VN-Index</strong>
        <div className="period-chips" role="group" aria-label="Kỳ biểu đồ">
          {(["1m", "3m", "1y"] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={period === p ? "signal-chip signal-chip--on" : "signal-chip"}
              aria-pressed={period === p}
              onClick={() => setPeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      {series.length >= 2 && (
        <MarketSpark series={series} period={period} />
      )}
      <div className="breadth-bar" aria-label="Độ rộng khuyến nghị">
        {ratings.map((r) => {
          const n = breadth[r.label] || 0;
          if (!n) return null;
          return (
            <span
              key={r.label}
              style={{ width: `${(n / total) * 100}%` }}
              title={`${r.label}: ${n}`}
              className={`rs-seg rating-${r.label.toLowerCase().includes("mạnh") ? "strong-buy" : r.label.toLowerCase().includes("mua") ? "buy" : r.label.toLowerCase().includes("giảm") ? "reduce" : r.label.toLowerCase().includes("bán") ? "sell" : "hold"}`}
            />
          );
        })}
      </div>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "4px 0 12px" }}>
        Phân bố khuyến nghị trên {allScores.length} mã có điểm
        {marketQ.data?.index?.close != null
          ? ` · VN-Index ${num(marketQ.data.index.close, 2)}`
          : ""}
      </p>
    </div>
  );
}

function MarketSpark({
  series,
  period,
}: {
  series: Array<{ time: string; close: number | null }>;
  period: "1m" | "3m" | "1y";
}) {
  const take = period === "1m" ? 22 : period === "3m" ? 66 : series.length;
  const vals = series
    .slice(-take)
    .map((p) => p.close)
    .filter((v): v is number => typeof v === "number");
  if (vals.length < 2) return null;
  const w = 280;
  const h = 64;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const pts = vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * (w - 2) + 1;
      const y = h - 2 - ((v - min) / span) * (h - 4);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden className="home-vnindex">
      <polyline fill="none" stroke="var(--accent)" strokeWidth="2" points={pts} />
    </svg>
  );
}

function RankCells({
  row,
  profile,
  ratings,
}: {
  row: RankingRow;
  profile: Profile;
  ratings: ReturnType<typeof ratingsFromMeta>;
}) {
  return (
    <>
      <div className="c-sym">
        <Link className="sym" to={`/t/${row.ticker}?profile=${profile}`}>
          {row.ticker}
        </Link>
      </div>
      <div className="c-name muted">{row.name || "—"}</div>
      <div className="c-sec muted">{sectorVi(row.sector)}</div>
      <div className="c-score tabular">{score(row.score)}</div>
      <div className="c-ruler">
        <ScoreRuler
          compact
          ratings={ratings}
          markers={
            row.score != null
              ? [{ value: row.score, label: row.ticker, kind: "primary" }]
              : []
          }
          aria-label={`Điểm ${row.ticker}`}
        />
      </div>
      <div className={`c-rating ${ratingClass(row.rating)}`}>{row.rating}</div>
      <div className="c-pillars">
        <PillarBars scores={row.scores} />
      </div>
      <div className="c-price tabular">{vnd(row.price ?? null)}</div>
      <div className="c-opp tabular">
        {typeof row.rewards_count === "number" ? `★ ${row.rewards_count}` : "—"}
      </div>
      <div className="c-risk tabular">
        {typeof row.risks_count === "number" ? `▲ ${row.risks_count}` : "—"}
      </div>
      <div className="c-counts-mobile muted">
        {typeof row.rewards_count === "number" || typeof row.risks_count === "number"
          ? `★ ${row.rewards_count ?? "—"} · ▲ ${row.risks_count ?? "—"}`
          : null}
      </div>
    </>
  );
}

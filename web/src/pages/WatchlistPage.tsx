/**
 * Danh sách theo dõi — localStorage, bảng live + pane chi tiết.
 * Không nhãn DCF undervalued/overvalued.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile, WatchlistItem } from "../api/types";
import { ScoreRuler } from "../components/ScoreRuler";
import { LiveChangePct, LivePrice } from "../live/LivePrice";
import { useLiveQuotes } from "../live/LiveContext";
import { dateVi, num, pct, score } from "../fmt";
import { ratingsFromMeta } from "../ratings";
import { loadWatchlist, saveWatchlist, WATCHLIST_MAX } from "../watchlist/storage";
import { buildRiskOpportunity } from "../riskOpportunity";

type SortKey = "symbol" | "price" | "change_pct" | "score" | "div" | "ref";

export function WatchlistPage() {
  const [sp] = useSearchParams();
  const profile = (sp.get("profile") as Profile) || "long_term";
  const [symbols, setSymbols] = useState<string[]>(() => loadWatchlist());
  const [sort, setSort] = useState<SortKey>("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<string | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const liveMap = useLiveQuotes(symbols);

  const summaryQ = useQuery({
    queryKey: ["watchlist-summary", symbols.join(","), profile],
    queryFn: () => api.watchlistSummary(symbols, profile),
    enabled: symbols.length > 0,
    refetchInterval: 30_000,
  });

  const metaQ = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const ratings = ratingsFromMeta(metaQ.data);

  const rows = useMemo(() => {
    const items = summaryQ.data?.items || [];
    const bySym = new Map(items.map((i) => [i.symbol, i]));
    const merged: WatchlistItem[] = symbols.map((s) => {
      const base = bySym.get(s) || { symbol: s };
      const live = liveMap[s];
      if (!live) return base;
      return {
        ...base,
        price: {
          value: live.price ?? base.price?.value ?? null,
          basis: live.basis || "live",
        },
        change_pct: {
          value: live.change_pct ?? base.change_pct?.value ?? null,
        },
        state: live.state,
      };
    });
    const dir = order === "asc" ? 1 : -1;
    const keyNum = (r: WatchlistItem, k: SortKey): number => {
      if (k === "symbol") return 0;
      if (k === "price") return r.price?.value ?? -Infinity;
      if (k === "change_pct") return r.change_pct?.value ?? -Infinity;
      if (k === "score") return r.score ?? -Infinity;
      if (k === "div") return r.dividend_yield?.value ?? -Infinity;
      if (k === "ref") return r.sector_ref?.gap_pct ?? -Infinity;
      return 0;
    };
    return [...merged].sort((a, b) => {
      if (sort === "symbol") return dir * a.symbol.localeCompare(b.symbol);
      return dir * (keyNum(a, sort) - keyNum(b, sort));
    });
  }, [symbols, summaryQ.data, liveMap, sort, order]);

  const onSort = (k: SortKey) => {
    if (sort === k) setOrder((o) => (o === "asc" ? "desc" : "asc"));
    else {
      setSort(k);
      setOrder(k === "symbol" ? "asc" : "desc");
    }
  };

  const remove = (sym: string) => {
    const next = saveWatchlist(symbols.filter((s) => s !== sym));
    setSymbols(next);
    if (selected === sym) setSelected(null);
  };

  const openDetail = (sym: string, el: HTMLElement) => {
    triggerRef.current = el;
    setSelected(sym);
  };

  const closeDetail = useCallback(() => {
    setSelected(null);
    triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: Event) => {
      if ((e as globalThis.KeyboardEvent).key === "Escape") closeDetail();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, closeDetail]);

  return (
    <main className="watchlist-page">
      <h1 style={{ margin: "0 0 8px", fontSize: "var(--fs-lg)", fontWeight: 600 }}>
        Theo dõi
      </h1>
      <p className="muted prose" style={{ marginTop: 0 }}>
        Tối đa {WATCHLIST_MAX} mã, lưu trên trình duyệt của bạn. Điểm M7 là EOD;
        giá trong phiên là tạm tính.
      </p>

      {symbols.length === 0 && (
        <div className="empty">
          Chưa có mã nào. Mở trang mã rồi nhấn ngôi sao, hoặc thêm từ ô tìm kiếm.
        </div>
      )}

      {symbols.length > 0 && (
        <div className={`watchlist-layout${selected ? " watchlist-layout--detail" : ""}`}>
          <div className="table-wrap">
            <table className="fin-table watchlist-table">
              <thead>
                <tr>
                  <th>
                    <SortBtn label="Mã" active={sort === "symbol"} order={order} onClick={() => onSort("symbol")} />
                  </th>
                  <th>
                    <SortBtn label="Giá" active={sort === "price"} order={order} onClick={() => onSort("price")} />
                  </th>
                  <th>
                    <SortBtn label="% 1 ngày" active={sort === "change_pct"} order={order} onClick={() => onSort("change_pct")} />
                  </th>
                  <th>
                    <SortBtn label="Điểm / hạng" active={sort === "score"} order={order} onClick={() => onSort("score")} />
                  </th>
                  <th>
                    <SortBtn label="Cổ tức" active={sort === "div"} order={order} onClick={() => onSort("div")} />
                  </th>
                  <th>
                    <SortBtn label="Tham chiếu ngành" active={sort === "ref"} order={order} onClick={() => onSort("ref")} />
                  </th>
                  <th>
                    <span className="sr-only">Xóa</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.symbol}
                    tabIndex={0}
                    className={selected === r.symbol ? "wl-row wl-row--on" : "wl-row"}
                    onClick={(e) => openDetail(r.symbol, e.currentTarget)}
                    onKeyDown={(e: KeyboardEvent<HTMLTableRowElement>) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openDetail(r.symbol, e.currentTarget);
                      }
                    }}
                  >
                    <td>
                      <Link
                        to={`/t/${r.symbol}?profile=${profile}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {r.symbol}
                      </Link>
                    </td>
                    <td>
                      <LivePrice value={r.price?.value ?? null} />
                    </td>
                    <td>
                      <LiveChangePct value={r.change_pct?.value ?? null} />
                    </td>
                    <td className="tabular">
                      {r.score != null ? (
                        <>
                          {score(r.score)}
                          {r.rank != null ? (
                            <span className="muted">
                              {" "}
                              ({r.rank}/{r.total_scored ?? "—"})
                            </span>
                          ) : null}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="tabular">
                      {r.dividend_yield?.value != null
                        ? pct(r.dividend_yield.value)
                        : "—"}
                    </td>
                    <td>
                      {r.sector_ref?.unreliable || r.sector_ref?.label === "Chưa đủ tin cậy" ? (
                        <span className="muted">Chưa đủ tin cậy</span>
                      ) : r.sector_ref?.gap_pct != null ? (
                        <span className="tabular">
                          {r.sector_ref.gap_pct >= 0 ? "+" : ""}
                          {num(r.sector_ref.gap_pct, 1)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="wl-remove"
                        aria-label={`Xóa ${r.symbol} khỏi theo dõi`}
                        onClick={(e) => {
                          e.stopPropagation();
                          remove(r.symbol);
                        }}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selected && (
            <WatchDetail
              symbol={selected}
              profile={profile}
              ratings={ratings}
              onClose={closeDetail}
            />
          )}
        </div>
      )}
    </main>
  );
}

function SortBtn({
  label,
  active,
  order,
  onClick,
}: {
  label: string;
  active: boolean;
  order: "asc" | "desc";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="sort-btn"
      onClick={onClick}
      aria-sort={active ? (order === "desc" ? "descending" : "ascending") : "none"}
    >
      {label}
    </button>
  );
}

function WatchDetail({
  symbol,
  profile,
  ratings,
  onClose,
}: {
  symbol: string;
  profile: Profile;
  ratings: ReturnType<typeof ratingsFromMeta>;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const detailQ = useQuery({
    queryKey: ["ticker", symbol, profile],
    queryFn: () => api.ticker(symbol, profile),
  });
  const pricesQ = useQuery({
    queryKey: ["prices-3m", symbol],
    queryFn: () => api.prices(symbol, { range: "3m" }),
  });
  const checksQ = useQuery({
    queryKey: ["checks", symbol, profile],
    queryFn: () => api.checks(symbol, profile),
  });
  const debateQ = useQuery({
    queryKey: ["debate", symbol, profile],
    queryFn: () => api.debate(symbol, profile, false),
  });

  useEffect(() => {
    const root = panelRef.current;
    if (!root) return;
    const focusables = root.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const first = focusables[0];
    first?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Tab" || !focusables.length) return;
      const list = [...focusables];
      const i = list.indexOf(document.activeElement as HTMLElement);
      if (e.shiftKey && (i <= 0)) {
        e.preventDefault();
        list[list.length - 1]?.focus();
      } else if (!e.shiftKey && i === list.length - 1) {
        e.preventDefault();
        list[0]?.focus();
      }
    };
    root.addEventListener("keydown", onKey);
    return () => root.removeEventListener("keydown", onKey);
  }, [symbol]);

  const result = detailQ.data?.result;
  const closes =
    pricesQ.data?.ohlcv
      ?.map((b) => (typeof b.close === "number" ? b.close : null))
      .filter((v): v is number => v != null) || [];

  const checks = (checksQ.data?.rewards || [])
    .concat(checksQ.data?.risks || [])
    .slice(0, 3);

  const debate = debateQ.data;
  const sourceLabel =
    debate?.source && debate.source !== "template" ? "AI" : "Mẫu sẵn";

  const riskOpp = detailQ.data
    ? buildRiskOpportunity(detailQ.data)
    : { opportunities: [], risks: [] };

  return (
    <aside
      ref={panelRef}
      className="watch-detail"
      role="dialog"
      aria-modal="true"
      aria-label={`Chi tiết ${symbol}`}
    >
      <div className="watch-detail-head">
        <h2 style={{ margin: 0, fontSize: "var(--fs-md)" }}>
          <Link to={`/t/${symbol}?profile=${profile}`}>{symbol}</Link>
        </h2>
        <button type="button" className="wl-remove" onClick={onClose} aria-label="Đóng">
          Esc
        </button>
      </div>

      {closes.length >= 2 && <MiniSpark series={closes} />}

      {result?.score != null && (
        <ScoreRuler
          compact
          ratings={ratings}
          markers={[{ value: result.score, label: symbol, kind: "primary" }]}
          aria-label={`Điểm ${symbol}`}
        />
      )}

      <h3 className="watch-detail-h">Phép kiểm chính</h3>
      {checks.length === 0 ? (
        <p className="muted">Chưa có phép kiểm.</p>
      ) : (
        <ul className="watch-checks">
          {checks.map((c) => (
            <li key={c.id}>{c.label_vi || c.id}</li>
          ))}
        </ul>
      )}

      <h3 className="watch-detail-h">
        Luận điểm <span className="muted">({sourceLabel})</span>
      </h3>
      <div className="watch-debate">
        <div>
          <strong>Tích cực</strong>
          <ul>
            {(debate?.bull || riskOpp.opportunities || [])
              .slice(0, 3)
              .map((b, i) => (
                <li key={i}>{typeof b === "string" ? b : b.text}</li>
              ))}
          </ul>
        </div>
        <div>
          <strong>Tiêu cực</strong>
          <ul>
            {(debate?.bear || riskOpp.risks || [])
              .slice(0, 3)
              .map((b, i) => (
                <li key={i}>{typeof b === "string" ? b : b.text}</li>
              ))}
          </ul>
        </div>
      </div>

      <p style={{ marginTop: 12 }}>
        <Link to={`/t/${symbol}?profile=${profile}`}>Xem trang đầy đủ</Link>
      </p>
      {detailQ.data?.asof && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Dữ liệu mã đến {dateVi(detailQ.data.asof)}
        </p>
      )}
    </aside>
  );
}

function MiniSpark({ series }: { series: number[] }) {
  const w = 240;
  const h = 48;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min || 1;
  const pts = series
    .map((v, i) => {
      const x = (i / (series.length - 1)) * (w - 2) + 1;
      const y = h - 2 - ((v - min) / span) * (h - 4);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} aria-hidden className="wl-spark">
      <polyline fill="none" stroke="var(--accent)" strokeWidth="1.5" points={pts} />
    </svg>
  );
}

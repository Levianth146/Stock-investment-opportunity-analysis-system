import { useMemo, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { num } from "../fmt";
import { LiveChangePct, LivePrice } from "../live/LivePrice";

type ListKey =
  | "strong_up"
  | "strong_down"
  | "volume_spike"
  | "high_52w"
  | "low_52w"
  | "overbought"
  | "oversold";

interface MoverRow {
  symbol: string;
  price?: { value?: number | null };
  change_pct?: { value?: number | null };
  relative_vol?: { value?: number | null };
  vol_ratio?: number;
  rsi14?: number;
}

const TABS: { key: ListKey; label: string }[] = [
  { key: "strong_up", label: "Tăng mạnh" },
  { key: "strong_down", label: "Giảm mạnh" },
  { key: "volume_spike", label: "Khối lượng đột biến" },
  { key: "high_52w", label: "Cao 52 tuần" },
  { key: "low_52w", label: "Thấp 52 tuần" },
  { key: "overbought", label: "RSI quá mua (EOD)" },
  { key: "oversold", label: "RSI quá bán (EOD)" },
];

function cellVal(v: { value?: number | null } | number | null | undefined): number | null {
  if (v == null) return null;
  if (typeof v === "number") return v;
  return v.value ?? null;
}

export function MoversGrid({
  lists,
  profile = "long_term",
  showMetrics = true,
}: {
  lists: Record<string, unknown> | null | undefined;
  profile?: string;
  /** false → cột % và Vol tương đối hiện "—" (không "+0%"). */
  showMetrics?: boolean;
}) {
  const [active, setActive] = useState<ListKey>("strong_up");
  const note =
    typeof lists?.liquidity_note === "string"
      ? lists.liquidity_note
      : "Lọc GTGD ≥ 1 tỷ đồng/ngày";

  const narrow =
    typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches;

  const panels = useMemo(() => {
    if (!lists) return [];
    return TABS.map((t) => ({
      ...t,
      rows: ((lists[t.key] as MoverRow[]) || []).slice(0, 10),
    }));
  }, [lists]);

  const shown = narrow ? panels.filter((p) => p.key === active) : panels.slice(0, 6);

  return (
    <section className="movers-grid" aria-label="Mã nổi bật">
      <div className="home-sec-head">
        <h2 className="home-sec-title">Mã nổi bật</h2>
        <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: 0 }}>
          {note}
        </p>
      </div>
      {narrow && (
        <div className="movers-tabs" role="tablist" aria-label="Loại danh sách">
          {TABS.slice(0, 6).map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={active === t.key}
              className={active === t.key ? "signal-chip signal-chip--on" : "signal-chip"}
              onClick={() => setActive(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <div className={`movers-panels${narrow ? " movers-panels--tabs" : ""}`}>
        {shown.map((p) => (
          <MoversTable
            key={p.key}
            title={p.label}
            rows={p.rows}
            profile={profile}
            showMetrics={showMetrics}
          />
        ))}
      </div>
    </section>
  );
}

function MoversTable({
  title,
  rows,
  profile,
  showMetrics,
}: {
  title: string;
  rows: MoverRow[];
  profile: string;
  showMetrics: boolean;
}) {
  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, sym: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      window.location.assign(`/t/${sym}?profile=${profile}`);
    }
  };

  return (
    <div className="movers-card">
      <h3 className="movers-title">{title}</h3>
      {rows.length === 0 ? (
        <p className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Không có mã đạt ngưỡng.
        </p>
      ) : (
        <table className="movers-table">
          <thead>
            <tr>
              <th scope="col">Mã</th>
              <th scope="col">Giá</th>
              <th scope="col">%</th>
              <th scope="col">Vol tương đối</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const sym = r.symbol;
              const rel = showMetrics
                ? (cellVal(r.relative_vol) ?? r.vol_ratio ?? null)
                : null;
              const chg = showMetrics ? cellVal(r.change_pct) : null;
              return (
                <tr
                  key={sym}
                  tabIndex={0}
                  onKeyDown={(e) => onKey(e, sym)}
                  className="movers-row"
                >
                  <td>
                    <Link to={`/t/${sym}?profile=${profile}`}>{sym}</Link>
                  </td>
                  <td>
                    <LivePrice value={cellVal(r.price)} digits={0} />
                  </td>
                  <td>
                    <LiveChangePct value={chg} />
                  </td>
                  <td className="tabular muted">
                    {rel != null ? num(rel, 1) + "×" : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

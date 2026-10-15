/** Sankey P&L (017c) — layout tự viết, không d3-sankey. */
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { IncomeFlowResponse } from "../api/types";
import { num, pct } from "../fmt";

type LaidNode = {
  id: string;
  label: string;
  kind: string;
  derived: boolean;
  value: number;
  pct_revenue: number | null;
  x: number;
  y: number;
  width: number;
  height: number;
};

type LaidLink = {
  source: string;
  target: string;
  value: number;
  pct_revenue: number | null;
  path: string;
  opacity: number;
};

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function useNarrow(breakpoint = 640): boolean {
  const [narrow, setNarrow] = useState(
    () =>
      typeof window !== "undefined" && window.matchMedia(`(max-width: ${breakpoint - 1}px)`).matches,
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const onChange = () => setNarrow(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [breakpoint]);
  return narrow;
}

/** Phân tầng trái → phải theo kind. */
function layoutSankey(
  data: IncomeFlowResponse,
  width: number,
  height: number,
): { nodes: LaidNode[]; links: LaidLink[] } {
  const nodes = data.nodes || [];
  const links = data.links || [];
  if (!nodes.length) return { nodes: [], links: [] };

  const colIds: string[][] = [[], [], []];
  for (const n of nodes) {
    if (n.kind === "source" || n.kind === "other_income") colIds[0]!.push(n.id);
    else if (n.kind === "intermediate") colIds[1]!.push(n.id);
    else colIds[2]!.push(n.id);
  }
  if (!colIds[1]!.length) {
    colIds[1] = colIds[2]!;
    colIds[2] = [];
  }

  const nodeW = 12;
  const labelPad = 110;
  const padY = 10;
  const usableH = height - padY * 2;
  const cols = colIds.filter((c) => c.length > 0);
  const innerW = width - labelPad * 2;
  const gapX =
    cols.length <= 1 ? 0 : (innerW - nodeW * cols.length) / (cols.length - 1);

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const laid = new Map<string, LaidNode>();

  cols.forEach((ids, ci) => {
    const total = ids.reduce((a, id) => a + (byId.get(id)?.value ?? 0), 0) || 1;
    let y = padY;
    const gap = Math.max(6, Math.min(14, usableH / Math.max(ids.length * 3, 1)));
    const scale = (usableH - gap * Math.max(ids.length - 1, 0)) / total;
    ids.forEach((id) => {
      const n = byId.get(id)!;
      const h = Math.max(6, n.value * scale);
      laid.set(id, {
        id: n.id,
        label: n.label,
        kind: n.kind,
        derived: !!n.derived,
        value: n.value,
        pct_revenue: n.pct_revenue,
        x: labelPad + ci * (nodeW + gapX),
        y,
        width: nodeW,
        height: h,
      });
      y += h + gap;
    });
  });

  const srcOutY = new Map<string, number>();
  const tgtInY = new Map<string, number>();
  for (const n of laid.values()) {
    srcOutY.set(n.id, n.y);
    tgtInY.set(n.id, n.y);
  }

  const sortedLinks = [...links].sort((a, b) => {
    const ay = laid.get(a.target)?.y ?? 0;
    const by = laid.get(b.target)?.y ?? 0;
    return ay - by;
  });

  const laidLinks: LaidLink[] = [];
  const maxVal = Math.max(...links.map((l) => l.value), 1);

  for (const lk of sortedLinks) {
    const s = laid.get(lk.source);
    const t = laid.get(lk.target);
    if (!s || !t) continue;
    const thick = Math.max(2, (lk.value / maxVal) * Math.min(s.height, 36));
    const y0 = srcOutY.get(lk.source) ?? s.y;
    const y1 = tgtInY.get(lk.target) ?? t.y;
    srcOutY.set(lk.source, y0 + thick);
    tgtInY.set(lk.target, y1 + thick);
    const x0 = s.x + s.width;
    const x1 = t.x;
    const mid = (x0 + x1) / 2;
    const path = `M${x0},${y0 + thick / 2} C${mid},${y0 + thick / 2} ${mid},${y1 + thick / 2} ${x1},${y1 + thick / 2}`;
    laidLinks.push({
      source: lk.source,
      target: lk.target,
      value: lk.value,
      pct_revenue: lk.pct_revenue,
      path,
      opacity: 0.35 + 0.35 * (lk.value / maxVal),
    });
  }

  return { nodes: [...laid.values()], links: laidLinks };
}

function nodeFill(kind: string): string {
  if (kind === "loss") return "var(--rating-sell)";
  if (kind === "other_income" || kind === "derived") return "var(--ink-3)";
  if (kind === "source" || kind === "intermediate") return "var(--series-1)";
  return "var(--series-2)";
}

function VerticalBars({ data }: { data: IncomeFlowResponse }) {
  const sinks = (data.nodes || []).filter(
    (n) =>
      n.kind === "sink" ||
      n.kind === "loss" ||
      n.kind === "derived" ||
      n.kind === "intermediate",
  );
  const maxPct = Math.max(
    ...sinks.map((n) => Math.abs(n.pct_revenue ?? 0)),
    0.01,
  );
  return (
    <div className="income-flow-bars" role="list" aria-label="Luồng theo phần trăm doanh thu">
      {sinks.map((n) => {
        const p = Math.abs(n.pct_revenue ?? 0);
        const w = (p / maxPct) * 100;
        return (
          <div className="income-flow-bar-row" key={n.id} role="listitem">
            <div className="income-flow-bar-lab">{n.label}</div>
            <div className="income-flow-bar-track">
              <div
                className={`income-flow-bar-fill${n.kind === "loss" ? " is-loss" : ""}`}
                style={{ width: `${Math.max(2, w)}%` }}
              />
            </div>
            <div className="income-flow-bar-val tabular">
              {num(n.value, 1)} ({pct(n.pct_revenue)})
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SankeySvg({
  data,
  focusId,
  onFocus,
}: {
  data: IncomeFlowResponse;
  focusId: string | null;
  onFocus: (id: string | null) => void;
}) {
  const width = 760;
  const sinkCount = (data.nodes || []).filter(
    (n) => n.kind === "sink" || n.kind === "loss" || n.kind === "derived",
  ).length;
  const height = Math.max(280, 40 + sinkCount * 36);
  const layout = useMemo(
    () => layoutSankey(data, width, height),
    [data, height],
  );
  const tip = focusId
    ? layout.nodes.find((n) => n.id === focusId)
    : null;
  const maxLink = Math.max(...layout.links.map((x) => x.value), 1);

  return (
    <div className="income-flow-svg-wrap">
      <svg
        className="income-flow-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Luồng doanh thu đến lợi nhuận"
      >
        {layout.links.map((lk, i) => (
          <path
            key={`${lk.source}-${lk.target}-${i}`}
            d={lk.path}
            fill="none"
            stroke="var(--series-1)"
            strokeWidth={Math.max(2, (lk.value / maxLink) * 20)}
            opacity={
              focusId && focusId !== lk.source && focusId !== lk.target
                ? 0.12
                : lk.opacity
            }
          />
        ))}
        {layout.nodes.map((n) => {
          const isLeft =
            n.kind === "source" || n.kind === "other_income";
          const labelX = isLeft ? n.x - 6 : n.x + n.width + 6;
          const anchor = isLeft ? "end" : "start";
          const labelY = n.y + Math.max(10, Math.min(n.height * 0.55, 14));
          return (
            <g key={n.id}>
              <rect
                x={n.x}
                y={n.y}
                width={n.width}
                height={n.height}
                fill={nodeFill(n.kind)}
                tabIndex={0}
                role="button"
                aria-label={`${n.label}: ${num(n.value, 1)} tỷ đồng, ${pct(n.pct_revenue)} doanh thu`}
                onMouseEnter={() => onFocus(n.id)}
                onMouseLeave={() => onFocus(null)}
                onFocus={() => onFocus(n.id)}
                onBlur={() => onFocus(null)}
              />
              <text
                x={labelX}
                y={labelY}
                textAnchor={anchor}
                className="income-flow-label"
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
      {tip && (
        <div className="income-flow-tooltip tabular" role="tooltip">
          {tip.label}: {num(tip.value, 1)} tỷ đồng ({pct(tip.pct_revenue)} doanh thu)
          {tip.derived ? " — phái sinh" : ""}
        </div>
      )}
    </div>
  );
}

function YearControls({
  periods,
  period,
  onChange,
}: {
  periods: string[];
  period: string;
  onChange: (p: string) => void;
}) {
  const years = periods.filter((p) => p !== "TTM");
  const hasTtm = periods.includes("TTM");
  const yearIdx = Math.max(0, years.indexOf(period === "TTM" ? years[years.length - 1]! : period));

  return (
    <div className="income-flow-controls">
      <div className="income-flow-slider-row">
        <label htmlFor="income-flow-year" className="income-flow-slider-lab">
          Năm
        </label>
        <input
          id="income-flow-year"
          type="range"
          min={0}
          max={Math.max(years.length - 1, 0)}
          step={1}
          value={period === "TTM" ? years.length - 1 : yearIdx}
          disabled={!years.length}
          aria-valuetext={period === "TTM" ? "TTM" : period}
          onChange={(e) => {
            const i = Number(e.target.value);
            const y = years[i];
            if (y) onChange(y);
          }}
        />
        <div className="income-flow-year-labels">
          {years.map((y) => (
            <button
              key={y}
              type="button"
              className={`income-flow-year-chip${period === y ? " is-active" : ""}`}
              aria-pressed={period === y}
              onClick={() => onChange(y)}
            >
              {y}
            </button>
          ))}
        </div>
      </div>
      {hasTtm && (
        <button
          type="button"
          className={`income-flow-ttm${period === "TTM" ? " is-active" : ""}`}
          aria-pressed={period === "TTM"}
          onClick={() => onChange("TTM")}
        >
          TTM
        </button>
      )}
    </div>
  );
}

function SummaryTable({ data }: { data: IncomeFlowResponse }) {
  const s = data.summary;
  if (!s) return null;
  const rows: Array<{ lab: string; cur: number | null; prior: number | null }> = [
    { lab: "Biên gộp", cur: s.gross_margin, prior: s.gross_margin_prior },
    { lab: "Biên LNST", cur: s.net_margin, prior: s.net_margin_prior },
    {
      lab: "Chi phí / doanh thu",
      cur: s.expense_to_revenue,
      prior: s.expense_to_revenue_prior,
    },
  ];
  return (
    <table className="income-flow-summary fin-table tabular">
      <thead>
        <tr>
          <th>Chỉ số</th>
          <th>Kỳ này</th>
          <th>{s.prior_label || "Kỳ trước"}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.lab}>
            <td>{r.lab}</td>
            <td>{pct(r.cur)}</td>
            <td>{pct(r.prior)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function IncomeFlowPanel({
  symbol,
  isBank,
}: {
  symbol: string;
  isBank?: boolean;
}) {
  const [period, setPeriod] = useState<string>("TTM");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [fade, setFade] = useState(false);
  const narrow = useNarrow(640);

  const q = useQuery({
    queryKey: ["income-flow", symbol, period],
    queryFn: () => api.incomeFlow(symbol, period),
    enabled: !!symbol && !isBank,
  });

  // Khi API trả available_periods, nếu TTM không có thì chọn năm cuối
  useEffect(() => {
    const periods = q.data?.available_periods;
    if (!periods?.length) return;
    if (!periods.includes(period)) {
      const fallback =
        periods.filter((p) => p !== "TTM").slice(-1)[0] || periods[0]!;
      setPeriod(fallback);
    }
  }, [q.data?.available_periods, period]);

  const changePeriod = (p: string) => {
    if (p === period) return;
    if (!prefersReducedMotion()) {
      setFade(true);
      window.setTimeout(() => {
        setPeriod(p);
        setFade(false);
      }, 120);
    } else {
      setPeriod(p);
    }
  };

  if (isBank) {
    return (
      <section className="income-flow" aria-label="Luồng lợi nhuận">
        <h3>Luồng từ doanh thu đến lợi nhuận</h3>
        <p className="muted">Chưa hỗ trợ ngân hàng</p>
      </section>
    );
  }

  if (q.isLoading) return <div className="skeleton" aria-label="Đang tải luồng lợi nhuận" />;
  if (q.isError) {
    return (
      <div className="error-box">
        Không tải được luồng lợi nhuận. Tải lại trang hoặc chọn mã khác.
      </div>
    );
  }

  const data = q.data!;
  if (data.supported === false) {
    return (
      <section className="income-flow" aria-label="Luồng lợi nhuận">
        <h3>Luồng từ doanh thu đến lợi nhuận</h3>
        <p className="muted">{data.message || "Chưa hỗ trợ ngân hàng"}</p>
      </section>
    );
  }

  const periods = data.available_periods || [];
  const hasChart = (data.nodes || []).length > 0;

  return (
    <section className="income-flow" aria-label="Luồng lợi nhuận">
      <h3>Luồng từ doanh thu đến lợi nhuận</h3>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", maxWidth: "70ch" }}>
        Đơn vị tỷ đồng. «Khác (cân đối)» và «Thu nhập khác (ròng)» là phái sinh để bảo toàn luồng, không phải chỉ tiêu BCTC.
      </p>
      <YearControls periods={periods} period={period} onChange={changePeriod} />
      <div className={`income-flow-chart${fade ? " is-fading" : ""}`}>
        {!hasChart ? (
          <div className="empty">
            Chưa đủ dữ liệu cho kỳ này. Chọn năm khác hoặc đợi snapshot cập nhật.
          </div>
        ) : narrow ? (
          <VerticalBars data={data} />
        ) : (
          <SankeySvg data={data} focusId={focusId} onFocus={setFocusId} />
        )}
      </div>
      <SummaryTable data={data} />
      {!!data.notes?.length && (
        <ul className="income-flow-notes muted">
          {data.notes.slice(0, 6).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

import { useMemo } from "react";
import { priceKind, priceKindWord } from "../live/staleness";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useLiveQuotes } from "../live/LiveContext";
import { formatQuarterLabel } from "../charts/FinCharts";
import {
  narrateFundamental,
  ratiosOf,
  structureOf,
  type Period,
  type StructureQ,
} from "../fundamental/analysis";

interface Seg { key: string; label: string; color: string; val: (s: StructureQ) => number }

const ASSET_SEGS: Seg[] = [
  { key: "cash", label: "Tiền", color: "#0b6e87", val: (s) => s.cash },
  { key: "inv", label: "Hàng tồn kho", color: "#4aa3b8", val: (s) => s.inventory },
  { key: "oc", label: "TS ngắn hạn khác", color: "#9cc9d4", val: (s) => s.otherCurrent },
  { key: "nc", label: "TS dài hạn", color: "#c9d6dc", val: (s) => s.nonCurrentAssets },
];
const FUND_SEGS: Seg[] = [
  { key: "cl", label: "Nợ ngắn hạn", color: "#c45c26", val: (s) => s.currentLiab },
  { key: "nl", label: "Nợ dài hạn", color: "#e39a6b", val: (s) => s.nonCurrentLiab },
  { key: "eq", label: "Vốn chủ sở hữu", color: "#6c7f8c", val: (s) => s.equity },
];

function StackedBars({ title, segs, rows }: { title: string; segs: Seg[]; rows: StructureQ[] }) {
  const W = 320;
  const H = 150;
  const bw = Math.min(40, (W - 20) / rows.length - 8);
  return (
    <figure className="fa-chart">
      <figcaption className="fa-chart-title">{title} (% tổng tài sản)</figcaption>
      <svg viewBox={`0 0 ${W} ${H + 22}`} width="100%" role="img" aria-label={title}>
        {rows.map((r, i) => {
          const x = 10 + i * ((W - 20) / rows.length) + 4;
          let y = H;
          return (
            <g key={String(r.period)}>
              {segs.map((s) => {
                const h = (s.val(r) / r.totalAssets) * H;
                y -= h;
                return <rect key={s.key} x={x} y={y} width={bw} height={Math.max(h, 0)} fill={s.color}><title>{`${s.label}: ${((s.val(r) / r.totalAssets) * 100).toFixed(0)}%`}</title></rect>;
              })}
              <text x={x + bw / 2} y={H + 14} fontSize="10" textAnchor="middle" fill="var(--ink-2)">
                {formatQuarterLabel(r.period)}
              </text>
            </g>
          );
        })}
      </svg>
      <ul className="heat-legend">
        {segs.map((s) => (
          <li key={s.key}><span className="heat-legend-sw" style={{ background: s.color }} />{s.label}</li>
        ))}
      </ul>
    </figure>
  );
}

const fmt = (x: number | null, d = 1) => (x == null ? "—" : x.toLocaleString("vi-VN", { maximumFractionDigits: d, minimumFractionDigits: d }));

export function FundamentalSummary({
  symbol,
  isFinancial,
  shares,
  priceClose,
}: {
  symbol: string;
  isFinancial: boolean;
  shares: number | null;
  priceClose: number | null;
}) {
  const fq = useQuery({ queryKey: ["financials", symbol], queryFn: () => api.financials(symbol) });
  const pq = useQuery({ queryKey: ["peers", symbol], queryFn: () => api.peers(symbol) });
  const quote = useLiveQuotes([symbol])[symbol];
  const kind = priceKind(quote);
  const price = kind !== "eod" ? quote!.price! : priceClose;

  // API trả tỷ VND (đã chia 1e9, kể cả EPS) → đưa về VND để P/E, P/B, vốn hoá cùng đơn vị với giá.
  const quarters = useMemo<Period[]>(
    () =>
      (fq.data?.quarterly || []).map((p) => ({
        period: p.period,
        items: Object.fromEntries(
          Object.entries(p.items || {}).map(([k, v]) => [k, typeof v === "number" ? v * 1e9 : v]),
        ),
      })) as Period[],
    [fq.data],
  );
  const structs = useMemo(
    () => quarters.map(structureOf).filter((s): s is StructureQ => s != null).slice(-5),
    [quarters],
  );
  const ratios = useMemo(
    () => ratiosOf(quarters, price ?? null, kind, shares),
    [quarters, price, kind, shares],
  );
  const med = pq.data?.sector_medians;
  const blocks = useMemo(
    () =>
      narrateFundamental({
        s: structs.length ? structs[structs.length - 1]! : null,
        prev: structs.length > 1 ? structs[structs.length - 2]! : null,
        r: ratios,
        sectorPe: med?.median_pe ?? null,
        sectorPb: med?.median_pb ?? null,
        isFinancial,
      }),
    [structs, ratios, med, isFinancial],
  );

  if (fq.isLoading) return <div className="skeleton" aria-busy="true" />;
  if (fq.isError || !quarters.length)
    return <p className="muted">Chưa có báo cáo tài chính theo quý cho mã này.</p>;

  const latest = quarters[quarters.length - 1]!;
  return (
    <section className="fa-summary" aria-label="Phân tích cơ bản">
      <p className="muted ta-basis">
        Báo cáo quý gần nhất: {formatQuarterLabel(latest.period)}.{" "}
        {kind === "eod"
          ? "Vốn hoá, P/E, P/B tính theo giá đóng cửa (chưa có giá trực tiếp)."
          : `Vốn hoá, P/E, P/B tính theo ${priceKindWord(kind)}.`}
      </p>
      <dl className="co-facts">
        <div><dt>Giá dùng để tính</dt><dd className="tabular">{fmt(price ?? null, 0)}</dd></div>
        <div><dt>Vốn hoá</dt><dd className="tabular">{ratios.marketCap != null ? `${fmt(ratios.marketCap / 1e9, 0)} tỷ` : "—"}</dd></div>
        <div><dt>P/E (4 quý)</dt><dd className="tabular">{fmt(ratios.pe)}{med?.median_pe ? ` · ngành ${fmt(med.median_pe)}` : ""}</dd></div>
        <div><dt>P/B</dt><dd className="tabular">{fmt(ratios.pb, 2)}{med?.median_pb ? ` · ngành ${fmt(med.median_pb, 2)}` : ""}</dd></div>
        <div><dt>ROE</dt><dd className="tabular">{ratios.roe != null ? `${fmt(ratios.roe)}%` : "—"}</dd></div>
        <div><dt>Biên LN ròng</dt><dd className="tabular">{ratios.netMargin != null ? `${fmt(ratios.netMargin)}%` : "—"}</dd></div>
        <div><dt>Nợ phải trả/VCSH</dt><dd className="tabular">{fmt(ratios.liabToEquity, 2)}</dd></div>
        {!isFinancial && <div><dt>Thanh khoản hiện hành</dt><dd className="tabular">{fmt(ratios.currentRatio, 2)}</dd></div>}
      </dl>
      {structs.length > 0 && (
        <div className="fa-charts">
          {!isFinancial && <StackedBars title="Cơ cấu tài sản" segs={ASSET_SEGS} rows={structs} />}
          <StackedBars title="Cơ cấu nguồn vốn" segs={FUND_SEGS} rows={structs} />
        </div>
      )}
      <h3 className="ta-h">Diễn giải</h3>
      <dl className="ta-narr">
        {blocks.map((b) => (
          <div key={b.head}>
            <dt>{b.head}</dt>
            <dd>{b.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

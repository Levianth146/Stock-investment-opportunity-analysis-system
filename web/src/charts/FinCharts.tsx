import { useEffect, useMemo, useRef, useState } from "react";
import type { FinancialPeriod } from "../api/types";
import { num, pct } from "../fmt";

/** Nhãn gọn trên cột — số đã ở đơn vị tỷ đồng hoặc tỷ lệ. */
function compactLabel(v: number): string {
  const a = Math.abs(v);
  if (a >= 100) return num(v, 0);
  if (a >= 10) return num(v, 1);
  return num(v, 1);
}

/** "2026Q2" / "2026-Q2" → "Q2/26" */
export function formatQuarterLabel(period: string | number): string {
  const s = String(period);
  const m = s.match(/^(20\d{2})\s*Q\s*([1-4])$/i) || s.match(/^(20\d{2})-Q([1-4])$/i);
  if (m && m[1] && m[2]) return `Q${m[2]}/${m[1].slice(2)}`;
  if (/^\d{4}$/.test(s)) return s.slice(2);
  return s;
}

/** Số nhãn trục x theo bề rộng (tránh chồng). */
export function maxXLabels(widthPx: number, n: number): number {
  if (widthPx < 400) return Math.min(4, n);
  if (widthPx < 700) return Math.min(6, n);
  return n;
}

function BarPair({
  labels,
  a,
  b,
  aLabel,
  bLabel,
  title,
  formatLab = (s: string) => s,
}: {
  labels: string[];
  a: (number | null)[];
  b: (number | null)[];
  aLabel: string;
  bLabel: string;
  title: string;
  formatLab?: (s: string) => string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && Number.isFinite(w)) setWidth(w);
    });
    ro.observe(el);
    setWidth(el.clientWidth || 640);
    return () => ro.disconnect();
  }, []);

  const max = Math.max(
    1,
    ...a.filter((x): x is number => x != null).map(Math.abs),
    ...b.filter((x): x is number => x != null).map(Math.abs),
  );
  const showN = maxXLabels(width, labels.length);
  const step = Math.max(1, Math.ceil(labels.length / showN));

  return (
    <div className="fin-chart-block" ref={wrapRef} style={{ minHeight: 200 }}>
      <h4 className="fin-chart-title">{title}</h4>
      <div className="chart-legend-row muted">
        <span>
          <i
            style={{
              display: "inline-block",
              width: 10,
              height: 4,
              background: "var(--series-1)",
              marginRight: 4,
              verticalAlign: "middle",
            }}
            aria-hidden
          />
          {aLabel}
        </span>
        <span>
          <i
            style={{
              display: "inline-block",
              width: 10,
              height: 4,
              background: "var(--series-2)",
              marginRight: 4,
              verticalAlign: "middle",
            }}
            aria-hidden
          />
          {bLabel}
        </span>
      </div>
      <div className="fin-bars" role="img" aria-label={title} style={{ minHeight: 160 }}>
        <div className="fin-bars-grid" aria-hidden />
        {labels.map((lab, i) => {
          const av = a[i];
          const bv = b[i];
          const ah = av == null ? 0 : (Math.abs(av) / max) * 100;
          const bh = bv == null ? 0 : (Math.abs(bv) / max) * 100;
          const showLab = i === 0 || i === labels.length - 1 || i % step === 0;
          return (
            <div className="fin-bar-col" key={`${lab}-${i}`}>
              <div className="fin-bar-toplabels">
                <span className="fin-bar-val">
                  {av == null ? "" : compactLabel(av)}
                </span>
                <span className="fin-bar-val">
                  {bv == null ? "" : compactLabel(bv)}
                </span>
              </div>
              <div className="fin-bar-pair">
                <div
                  className="fin-bar"
                  style={{
                    height: `${ah}%`,
                    background: "var(--series-1)",
                    opacity: av != null && av < 0 ? 0.45 : 1,
                  }}
                  title={`${aLabel}: ${av == null ? "—" : num(av, 1)}`}
                />
                <div
                  className="fin-bar"
                  style={{
                    height: `${bh}%`,
                    background: "var(--series-2)",
                    opacity: bv != null && bv < 0 ? 0.45 : 1,
                  }}
                  title={`${bLabel}: ${bv == null ? "—" : num(bv, 1)}`}
                />
              </div>
              <span className="fin-bar-lab muted">
                {showLab ? formatLab(lab) : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Đường biên / ROE — 3 vạch y + đơn vị %; nhãn x thưa theo bề rộng. */
function MarginLine({
  labels,
  values,
  title,
  format = (v: number) => pct(v, { digits: 0 }),
  formatLab = (s: string) => s,
}: {
  labels: string[];
  values: (number | null)[];
  title: string;
  format?: (v: number) => string;
  formatLab?: (s: string) => string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && Number.isFinite(w)) setWidth(w);
    });
    ro.observe(el);
    setWidth(el.clientWidth || 640);
    return () => ro.disconnect();
  }, []);

  const nums = values.filter((x): x is number => x != null);
  if (!nums.length) return null;
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const n = Math.max(1, labels.length - 1);
  const w = Math.max(280, width || labels.length * 40);
  const h = 200;
  const padT = 22;
  const padB = 28;
  const padL = 36;
  const padR = 12;
  const plotH = h - padT - padB;
  const showN = maxXLabels(width, labels.length);
  const step = Math.max(1, Math.ceil(labels.length / showN));

  const coords = values.map((v, i) => {
    if (v == null) return null;
    const x = padL + (i / n) * (w - padL - padR);
    const y = padT + plotH - ((v - min) / span) * plotH;
    return { x, y, v, i };
  });

  const pts = coords
    .filter((p): p is { x: number; y: number; v: number; i: number } => p != null)
    .map((p) => `${p.x},${p.y}`)
    .join(" ");

  const yTicks = [0, 0.5, 1].map((t) => min + span * t);

  return (
    <div className="fin-chart-block fin-chart-block--small" ref={wrapRef} style={{ minHeight: 200 }}>
      <h4 className="fin-chart-title">{title}</h4>
      <svg
        width="100%"
        viewBox={`0 0 ${w} ${h}`}
        className="fin-spark"
        role="img"
        aria-label={title}
        style={{ minHeight: 200 }}
      >
        {yTicks.map((tv, ti) => {
          const y = padT + plotH - ((tv - min) / span) * plotH;
          return (
            <g key={ti}>
              <line
                x1={padL}
                x2={w - padR}
                y1={y}
                y2={y}
                stroke="var(--ink-3)"
                strokeOpacity={0.15}
                strokeWidth="1"
              />
              <text x={2} y={y + 3} className="fin-spark-axis">
                {format(tv)}
              </text>
            </g>
          );
        })}
        <polyline
          fill="none"
          stroke="var(--series-1)"
          strokeWidth="2"
          points={pts}
        />
        {coords.map((p) => {
          if (p == null) return null;
          const isLast = p.i === labels.length - 1;
          const showLab = p.i === 0 || isLast || p.i % step === 0;
          const anchor = p.i === 0 ? "start" : isLast ? "end" : "middle";
          // Nhãn cuối đẩy lên/trái để không đè đường (45%)
          const labY = isLast ? p.y - 10 : p.y - 7;
          const labX = isLast ? p.x - 4 : p.x;
          return (
            <g key={p.i}>
              <circle cx={p.x} cy={p.y} r={2.5} fill="var(--series-1)">
                <title>{`${formatLab(labels[p.i] ?? "")}: ${format(p.v)}`}</title>
              </circle>
              {isLast && (
                <text
                  x={labX}
                  y={labY}
                  textAnchor="end"
                  className="fin-spark-lab"
                >
                  {format(p.v)}
                </text>
              )}
              {showLab && (
                <text
                  x={p.x}
                  y={h - 8}
                  textAnchor={anchor}
                  className="fin-spark-axis"
                >
                  {formatLab(labels[p.i] ?? "")}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/**
 * Một series cột — nhãn dính đỉnh cột; hỗ trợ âm (LNST) xuống dưới 0;
 * trục y 3 vạch. Số đã ở đơn vị tỷ đồng (API).
 */
function BarSingle({
  labels,
  values,
  title,
  colorVar = "var(--series-1)",
  formatLab = (s: string) => s,
}: {
  labels: string[];
  values: (number | null)[];
  title: string;
  colorVar?: string;
  formatLab?: (s: string) => string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && Number.isFinite(w)) setWidth(w);
    });
    ro.observe(el);
    setWidth(el.clientWidth || 640);
    return () => ro.disconnect();
  }, []);

  const nums = values.filter((x): x is number => x != null);
  const maxAbs = Math.max(1, ...nums.map(Math.abs));
  const hasNeg = nums.some((v) => v < 0);
  const showN = maxXLabels(width, labels.length);
  const step = Math.max(1, Math.ceil(labels.length / showN));
  const yTicks = hasNeg
    ? [
        { pos: 0, label: compactLabel(maxAbs) },
        { pos: 50, label: "0" },
        { pos: 100, label: compactLabel(-maxAbs) },
      ]
    : [
        { pos: 0, label: compactLabel(maxAbs) },
        { pos: 50, label: compactLabel(maxAbs / 2) },
        { pos: 100, label: "0" },
      ];

  return (
    <div className="fin-chart-block" ref={wrapRef} style={{ minHeight: 200 }}>
      <h4 className="fin-chart-title">{title}</h4>
      <div className="fin-bars-wrap">
        <div className="fin-yaxis" aria-hidden>
          {yTicks.map((t) => (
            <span key={t.pos} className="fin-yaxis-tick tabular">
              {t.label}
            </span>
          ))}
        </div>
        <div
          className={`fin-bars ${hasNeg ? "fin-bars--signed" : ""}`}
          role="img"
          aria-label={title}
          style={{ minHeight: 160 }}
        >
          <div className="fin-bars-grid" aria-hidden />
          {hasNeg && <div className="fin-zero-line" aria-hidden />}
          {labels.map((lab, i) => {
            const v = values[i];
            const showLab = i === 0 || i === labels.length - 1 || i % step === 0;
            if (v == null) {
              return (
                <div className="fin-bar-col" key={`${lab}-${i}`}>
                  <div className="fin-bar-toplabels" />
                  <div className="fin-bar-pair fin-bar-pair--single" />
                  <span className="fin-bar-lab muted">
                    {showLab ? formatLab(lab) : ""}
                  </span>
                </div>
              );
            }
            const hPct = (Math.abs(v) / maxAbs) * 100;
            const neg = v < 0;
            return (
              <div className="fin-bar-col" key={`${lab}-${i}`}>
                <div className="fin-bar-toplabels">
                  <span className="fin-bar-val">{neg ? "" : compactLabel(v)}</span>
                </div>
                {hasNeg ? (
                  <div className="fin-bar-signed" title={`${title}: ${num(v, 1)}`}>
                    <div className="fin-bar-half fin-bar-half--up">
                      {!neg && (
                        <div
                          className="fin-bar fin-bar--pos"
                          style={{ height: `${hPct}%`, background: colorVar }}
                        />
                      )}
                    </div>
                    <div className="fin-bar-half fin-bar-half--down">
                      {neg && (
                        <div
                          className="fin-bar fin-bar--neg"
                          style={{ height: `${hPct}%`, background: colorVar }}
                        />
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="fin-bar-pair fin-bar-pair--single">
                    <div
                      className="fin-bar fin-bar--pos"
                      style={{ height: `${hPct}%`, background: colorVar }}
                      title={`${title}: ${num(v, 1)}`}
                    />
                  </div>
                )}
                {neg && (
                  <div className="fin-bar-toplabels fin-bar-toplabels--below">
                    <span className="fin-bar-val">{compactLabel(v)}</span>
                  </div>
                )}
                <span className="fin-bar-lab muted">
                  {showLab ? formatLab(lab) : ""}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function QuarterlyFinCharts({ rows }: { rows: FinancialPeriod[] }) {
  const labels = useMemo(() => rows.map((r) => String(r.period)), [rows]);
  if (!rows.length) return <div className="empty">Chưa có dữ liệu quý.</div>;
  return (
    <div className="fin-charts">
      <div className="fin-charts-split">
        <BarSingle
          title="Doanh thu theo quý (tỷ đồng)"
          labels={labels}
          values={rows.map((r) => r.items.revenue ?? null)}
          colorVar="var(--series-1)"
          formatLab={formatQuarterLabel}
        />
        <BarSingle
          title="LNST theo quý (tỷ đồng)"
          labels={labels}
          values={rows.map((r) => r.items.net_income ?? null)}
          colorVar="var(--series-2)"
          formatLab={formatQuarterLabel}
        />
      </div>
      <MarginLine
        title="Biên gộp theo quý"
        labels={labels}
        values={rows.map((r) => r.gross_margin)}
        format={(v) => pct(v, { digits: 0 })}
        formatLab={formatQuarterLabel}
      />
    </div>
  );
}

export function AnnualFinCharts({ rows }: { rows: FinancialPeriod[] }) {
  if (!rows.length) return <div className="empty">Chưa có dữ liệu năm.</div>;
  const labels = rows.map((r) => String(r.period));
  return (
    <div className="fin-charts">
      <BarPair
        title="Doanh thu & LNST theo năm (tỷ đồng)"
        labels={labels}
        a={rows.map((r) => r.items.revenue ?? null)}
        b={rows.map((r) => r.items.net_income ?? null)}
        aLabel="Doanh thu"
        bLabel="LNST"
      />
      <MarginLine
        title="ROE theo năm"
        labels={labels}
        values={rows.map((r) => r.roe)}
        format={(v) => pct(v, { digits: 0 })}
      />
      <BarPair
        title="CFO & Capex / FCF (tỷ đồng)"
        labels={labels}
        a={rows.map((r) => r.items.cfo ?? null)}
        b={rows.map((r) => r.items.capex ?? null)}
        aLabel="CFO"
        bLabel="Capex"
      />
      <BarPair
        title="Nợ/VCSH & FCF (tỷ đồng)"
        labels={labels}
        a={rows.map((r) => r.debt_to_equity)}
        b={rows.map((r) => r.fcf)}
        aLabel="D/E"
        bLabel="FCF"
      />
    </div>
  );
}

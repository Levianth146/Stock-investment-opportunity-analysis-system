import { useMemo } from "react";
import type { FinancialPeriod } from "../api/types";
import { compactBillions, num, pct } from "../fmt";

export type DivYear = {
  period: string;
  dividends: number | null;
  netIncomeParent: number | null;
  implausible: boolean;
  payoutOver100: boolean;
};

function periodFlagged(r: FinancialPeriod): boolean {
  const flags = (r as { flags?: string[] }).flags || [];
  return flags.includes("dividends_implausible");
}

/** Chuẩn hoá 10 năm gần nhất; null giữ nguyên (không thành 0). */
export function buildDividendSeries(rows: FinancialPeriod[], years = 10): DivYear[] {
  const sorted = [...rows]
    .filter((r) => String(r.period).match(/^\d{4}$/))
    .sort((a, b) => Number(a.period) - Number(b.period));
  const slice = sorted.slice(-years);
  return slice.map((r) => {
    const dividends = r.items.dividends_paid ?? null;
    const netIncomeParent =
      r.items.net_income_parent ?? r.items.net_income ?? null;
    const ratio =
      dividends != null &&
      netIncomeParent != null &&
      netIncomeParent > 0
        ? dividends / netIncomeParent
        : null;
    return {
      period: String(r.period),
      dividends,
      netIncomeParent,
      implausible: periodFlagged(r),
      payoutOver100: ratio != null && ratio > 1,
    };
  });
}

function payoutRatio(d: DivYear): number | null {
  if (d.implausible) return null;
  if (d.dividends == null || d.netIncomeParent == null || d.netIncomeParent <= 0) {
    return null;
  }
  return d.dividends / d.netIncomeParent;
}

export function summarizeDividends(series: DivYear[]): {
  consecutivePaid: number;
  avgPayout5y: number | null;
  hasAny: boolean;
  allNullOrZero: boolean;
  unreliable: boolean;
} {
  const recent6 = series.slice(-6);
  const flagged = recent6.filter((s) => s.implausible).length;
  const unreliable = recent6.length > 0 && flagged >= 3;

  const paid = series.map(
    (s) => !s.implausible && s.dividends != null && s.dividends > 0,
  );
  let consecutivePaid = 0;
  for (let i = paid.length - 1; i >= 0; i--) {
    if (!paid[i]) break;
    consecutivePaid += 1;
  }
  const last5 = series.slice(-5);
  const ratios = last5
    .map(payoutRatio)
    .filter((x): x is number => x != null && Number.isFinite(x));
  const avgPayout5y =
    ratios.length > 0 ? ratios.reduce((a, b) => a + b, 0) / ratios.length : null;
  const hasAny = series.some((s) => s.dividends != null && s.dividends !== 0);
  const allNullOrZero = series.every(
    (s) => s.dividends == null || s.dividends === 0,
  );
  return { consecutivePaid, avgPayout5y, hasAny, allNullOrZero, unreliable };
}

/**
 * API financials đã trả tỷ VND — dùng compactBillions trực tiếp, không chia 1e9 lần nữa.
 * Trục y: 3 vạch (0 / giữa / max).
 */
export function DividendCashBars({ series }: { series: DivYear[] }) {
  const nums = series
    .map((s) => s.dividends)
    .filter((x): x is number => x != null && x !== 0)
    .map(Math.abs);
  const max = Math.max(1, ...nums);
  const mid = max / 2;
  const yTicks = [
    { v: max, label: compactBillions(max) },
    { v: mid, label: compactBillions(mid) },
    { v: 0, label: compactBillions(0) },
  ];
  return (
    <div className="fin-chart-block">
      <h4 className="fin-chart-title">Cổ tức tiền mặt theo năm (tỷ đồng)</h4>
      <div className="fin-bars-wrap">
        <div className="fin-yaxis" aria-hidden>
          {yTicks.map((t) => (
            <span key={t.v} className="fin-yaxis-tick tabular">
              {t.label}
            </span>
          ))}
        </div>
        <div className="fin-bars fin-bars--div" role="img" aria-label="Cổ tức theo năm">
          <div className="fin-bars-grid" aria-hidden />
          {series.map((s) => {
            const v = s.dividends;
            const missing = v == null;
            const zero = v === 0;
            const h = missing || zero ? 0 : (Math.abs(v) / max) * 100;
            const faint = s.implausible;
            return (
              <div className="fin-bar-col" key={s.period}>
                <div className="fin-bar-toplabels">
                  <span className="fin-bar-val">
                    {missing || zero
                      ? ""
                      : `${compactBillions(v)}${faint ? " ?" : ""}`}
                  </span>
                </div>
                <div className="fin-bar-pair fin-bar-pair--single">
                  <div
                    className="fin-bar"
                    style={{
                      height: `${h}%`,
                      background: "var(--series-1)",
                      opacity: missing ? 0.15 : faint ? 0.35 : 1,
                    }}
                    title={
                      missing
                        ? `${s.period}: chưa có dữ liệu`
                        : faint
                          ? `${s.period}: số liệu bất thường, cần kiểm tra`
                          : zero
                            ? `${s.period}: 0`
                            : `${s.period}: ${compactBillions(v)}`
                    }
                  />
                </div>
                <span className="fin-bar-lab muted">{s.period}</span>
                {missing && (
                  <span className="fin-bar-note muted">chưa có dữ liệu</span>
                )}
                {faint && !missing && (
                  <span className="fin-bar-note muted">
                    Số liệu bất thường, cần kiểm tra
                  </span>
                )}
                {s.payoutOver100 && !faint && !missing && (
                  <span className="fin-bar-note muted">
                    Chi trả vượt LNST năm đó
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Tỷ lệ chi trả = cổ tức / LNST công ty mẹ — biểu đồ riêng (một trục y). */
export function DividendPayoutLine({ series }: { series: DivYear[] }) {
  const points = series.map((s) => ({
    period: s.period,
    v: payoutRatio(s),
    over: s.payoutOver100 && !s.implausible,
  }));
  const nums = points.map((p) => p.v).filter((x): x is number => x != null);
  if (!nums.length) return null;
  const min = Math.min(0, ...nums);
  const max = Math.max(...nums, 0.01);
  const span = max - min || 1;
  const n = Math.max(1, points.length - 1);
  const w = Math.max(280, points.length * 44);
  const h = 120;
  const padT = 20;
  const padB = 28;
  const padX = 28;
  const plotH = h - padT - padB;

  const coords = points.map((p, i) => {
    if (p.v == null) return null;
    const x = padX + (i / n) * (w - padX * 2);
    const y = padT + plotH - ((p.v - min) / span) * plotH;
    return { x, y, v: p.v, i, over: p.over };
  });
  const pts = coords
    .filter((c): c is { x: number; y: number; v: number; i: number; over: boolean } => c != null)
    .map((c) => `${c.x},${c.y}`)
    .join(" ");

  const yTicks = [0, 0.5, 1].filter((t) => t >= min - 0.01 && t <= max + 0.01);

  return (
    <div className="fin-chart-block fin-chart-block--small">
      <h4 className="fin-chart-title">Tỷ lệ chi trả (cổ tức / LNST mẹ)</h4>
      <svg
        width="100%"
        viewBox={`0 0 ${w} ${h}`}
        className="fin-spark"
        role="img"
        aria-label="Tỷ lệ chi trả"
        style={{ minHeight: 120 }}
      >
        {yTicks.map((t) => {
          const y = padT + plotH - ((t - min) / span) * plotH;
          return (
            <g key={t}>
              <line
                x1={padX}
                x2={w - padX}
                y1={y}
                y2={y}
                stroke="var(--ink-3)"
                strokeOpacity={0.15}
                strokeWidth="1"
              />
              <text x={4} y={y + 3} className="fin-spark-axis">
                {pct(t, { digits: 0 })}
              </text>
            </g>
          );
        })}
        <polyline
          fill="none"
          stroke="var(--series-2)"
          strokeWidth="2"
          points={pts}
        />
        {coords.map((c) => {
          if (c == null) return null;
          const isLast = c.i === points.length - 1;
          return (
            <g key={c.i}>
              <circle cx={c.x} cy={c.y} r={2.5} fill="var(--series-2)">
                <title>
                  {`${points[c.i]?.period ?? ""}: ${pct(c.v)}${
                    c.over ? " (chi trả vượt LNST năm đó)" : ""
                  }`}
                </title>
              </circle>
              {isLast && (
                <text
                  x={c.x}
                  y={c.y - 8}
                  textAnchor="end"
                  className="fin-spark-lab"
                >
                  {pct(c.v, { digits: 0 })}
                </text>
              )}
              <text
                x={c.x}
                y={h - 6}
                textAnchor={c.i === 0 ? "start" : isLast ? "end" : "middle"}
                className="fin-spark-axis"
              >
                {(points[c.i]?.period ?? "").slice(2)}
              </text>
            </g>
          );
        })}
      </svg>
      {points.some((p) => p.over) && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 4 }}>
          Có năm chi trả vượt LNST năm đó — vẫn vẽ để đối chiếu.
        </p>
      )}
    </div>
  );
}

export function DividendPanel({ rows }: { rows: FinancialPeriod[] }) {
  const series = useMemo(() => buildDividendSeries(rows, 10), [rows]);
  const summary = useMemo(() => summarizeDividends(series), [series]);

  if (!series.length || summary.allNullOrZero) {
    return (
      <p className="muted">Chưa có dữ liệu cổ tức cho mã này</p>
    );
  }

  if (summary.unreliable) {
    return (
      <p className="muted" role="status">
        Dữ liệu cổ tức chưa đáng tin cho mã này
      </p>
    );
  }

  return (
    <div className="fin-charts">
      <DividendCashBars series={series} />
      <DividendPayoutLine series={series} />
      <dl className="div-summary muted">
        <div>
          <dt>Số năm liên tiếp có trả</dt>
          <dd className="tabular">{summary.consecutivePaid}</dd>
        </div>
        <div>
          <dt>Tỷ lệ chi trả TB 5 năm</dt>
          <dd className="tabular">
            {summary.avgPayout5y != null
              ? pct(summary.avgPayout5y, { digits: 0 })
              : "—"}
          </dd>
        </div>
      </dl>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", maxWidth: "70ch" }}>
        Ô trống = chưa có dữ liệu (khác với trả 0). Tỷ lệ chi trả chỉ tính khi
        LNST công ty mẹ dương; năm gắn cờ bất thường không tính vào chuỗi liên
        tiếp và trung bình 5 năm.
      </p>
    </div>
  );
}

/** null ≠ 0 cho waterfall / bảng. Giá trị API đã là tỷ VND. */
export function formatDividendCell(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v === 0) return "0";
  return compactBillions(v);
}

export function formatPayoutCell(v: number | null | undefined): string {
  if (v == null) return "—";
  return num(v, 1);
}

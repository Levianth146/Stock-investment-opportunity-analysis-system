import { useMemo } from "react";
import { dateVi, num } from "../fmt";
import { LiveChangePct, LivePrice } from "../live/LivePrice";

export interface IndexPayload {
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
}

export function IndexStrip({
  index,
  asof,
}: {
  index: IndexPayload | null | undefined;
  asof?: string | null;
}) {
  const price = index?.price?.value ?? null;
  const chg = index?.change_pct?.value ?? null;
  const prev = index?.prev_close?.value ?? null;
  const label = index?.label || "EOD";

  const spark = useMemo(() => {
    const bars = index?.candles_1m || [];
    if (bars.length >= 2) {
      return bars.map((b) => b.c).filter((v) => typeof v === "number");
    }
    const eod = index?.series_eod || [];
    return eod
      .map((p) => p.close)
      .filter((v): v is number => typeof v === "number");
  }, [index]);

  if (price == null && !spark.length) {
    return (
      <section className="index-strip" aria-label="Chỉ số">
        <p className="muted">Chưa có dữ liệu VN-Index.</p>
      </section>
    );
  }

  return (
    <section className="index-strip" aria-label="VN-Index">
      <div className="index-strip-main">
        <span className="index-name">VN-Index</span>
        <LivePrice value={price} digits={2} className="index-price" />
        <LiveChangePct value={chg} />
        <span className="muted index-label">{label}</span>
      </div>
      {spark.length >= 2 && (
        <IndexSpark series={spark} prevClose={prev} up={(chg ?? 0) >= 0} />
      )}
      {asof && index?.source === "eod" && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "4px 0 0" }}>
          Phiên đóng gần nhất {dateVi(asof)}
        </p>
      )}
    </section>
  );
}

function IndexSpark({
  series,
  prevClose,
  up,
}: {
  series: number[];
  prevClose: number | null;
  up: boolean;
}) {
  const w = 320;
  const h = 56;
  const min = Math.min(...series, prevClose ?? series[0]!);
  const max = Math.max(...series, prevClose ?? series[0]!);
  const span = max - min || 1;
  const pts = series
    .map((v, i) => {
      const x = (i / (series.length - 1)) * (w - 2) + 1;
      const y = h - 2 - ((v - min) / span) * (h - 4);
      return `${x},${y}`;
    })
    .join(" ");
  const prevY =
    prevClose != null
      ? h - 2 - ((prevClose - min) / span) * (h - 4)
      : null;
  return (
    <svg
      className="index-spark"
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      role="img"
      aria-label={`Biểu đồ VN-Index, giá ${num(series[series.length - 1] ?? null, 2)}`}
    >
      {prevY != null && (
        <line
          x1={0}
          x2={w}
          y1={prevY}
          y2={prevY}
          stroke="var(--ink-3)"
          strokeWidth="1"
          strokeDasharray="4 3"
        />
      )}
      <polyline
        fill="none"
        stroke={up ? "var(--up)" : "var(--down)"}
        strokeWidth="2"
        points={pts}
      />
    </svg>
  );
}

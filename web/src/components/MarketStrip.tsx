import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { dateVi, num } from "../fmt";
import { useMarketStream } from "../live/useMarketStream";

/** VN-Index đóng cửa + sparkline 30 phiên — chỉ desktop. */
export function MarketStrip() {
  const q = useQuery({
    queryKey: ["market"],
    queryFn: () => api.market(),
    staleTime: 300_000,
  });

  // Không mở luồng ở đây — chỉ đọc nếu trang chủ đang giữ luồng sống.
  const { data: live, conn } = useMarketStream(false);
  const liveIdx = live?.index;
  // Có số từ luồng/poll (kể cả khi SSE bị chặn) và là dữ liệu hub (trực tiếp hoặc chốt phiên hôm nay).
  const isLive =
    (conn === "live" || (conn === "fallback" && !!live)) &&
    liveIdx?.price?.value != null &&
    liveIdx?.source === "realtime";
  const isRealtimeNow = isLive && live?.realtime?.state === "live" && liveIdx?.price?.basis === "live";

  const idx = q.data?.index;
  if (isLive && liveIdx) {
    const lc = liveIdx.change_pct?.value ?? null;
    const lup = lc != null && lc >= 0;
    return (
      <div className="market-strip" aria-label="VN-Index trực tiếp">
        <span className="ms-sym">VN-Index</span>
        <span className="tabular ms-close">{num(liveIdx.price?.value ?? null, 2)}</span>
        {lc != null && (
          <span className={`tabular ${lup ? "pos" : "neg"}`}>
            {lup ? "+" : ""}
            {num(lc, 2)}%
          </span>
        )}
        {isRealtimeNow ? (
          <span className="ms-live">● Trực tiếp</span>
        ) : (
          <span className="muted ms-asof">{liveIdx.label || "Đóng cửa (tạm tính)"}</span>
        )}
      </div>
    );
  }
  if (q.isError || !idx || idx.close == null) return null;

  const series = idx.series_30d || [];
  const change = idx.change_pct;
  const up = change != null && change >= 0;
  const labelDate = dateVi(idx.asof_session || q.data?.asof);

  return (
    <div className="market-strip" aria-label="VN-Index đóng cửa">
      <span className="ms-sym">VN-Index</span>
      <span className="tabular ms-close">{num(idx.close, 2)}</span>
      {change != null && (
        <span className={`tabular ${up ? "pos" : "neg"}`}>
          {up ? "+" : ""}
          {num(change, 2)}%
        </span>
      )}
      <span className="muted ms-asof">Đóng cửa {labelDate}</span>
      {series.length >= 2 && <MiniSpark series={series} up={up} />}
    </div>
  );
}

function MiniSpark({
  series,
  up,
}: {
  series: Array<{ time: string; close: number | null }>;
  up: boolean;
}) {
  const vals = series
    .map((p) => p.close)
    .filter((v): v is number => typeof v === "number");
  if (vals.length < 2) return null;
  const w = 72;
  const h = 22;
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
    <svg
      className="ms-spark"
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      aria-hidden
    >
      <polyline
        fill="none"
        stroke={up ? "var(--up)" : "var(--down)"}
        strokeWidth="1.5"
        points={pts}
      />
    </svg>
  );
}

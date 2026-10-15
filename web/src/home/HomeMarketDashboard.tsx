import { useLive } from "../live/LiveContext";
import type { MarketConn } from "../live/marketStream";
import { useMarketStream } from "../live/useMarketStream";
import { bannerForState, canShowSessionMetrics } from "../live/staleness";
import { BreadthBars } from "./BreadthBars";
import { IndexStrip } from "./IndexStrip";
import { MoversGrid } from "./MoversGrid";
import { SectorHeatmap } from "./SectorHeatmap";

export function HomeMarketDashboard({ profile = "long_term" }: { profile?: string }) {
  const { status } = useLive();
  // Một luồng SSE /api/stream/market (full → delta); mất luồng thì poll 30s.
  const { data, conn } = useMarketStream(true);
  const rtState = String(data?.realtime?.state || status.state || "no_realtime");
  const phase = status.sessionPhase ?? data?.session?.phase ?? null;
  const reason = status.reason ?? null;
  const closeNote =
    phase === "closed" && data?.index?.price?.basis === "close"
      ? `Ngoài giờ giao dịch. Đang hiện giá chốt phiên (tạm tính) — ${data.index.label ?? "đóng cửa"}; số liệu EOD chính thức cập nhật sau.`
      : null;
  const banner =
    closeNote ||
    (phase === "lunch" ? "Nghỉ trưa — HOSE mở lại lúc 13:00. Đang hiện giá phiên sáng." : null) ||
    status.banner ||
    bannerForState(
      rtState === "live" && phase === "closed" ? "closed" : rtState,
      null,
      reason,
    );
  const showMetrics = canShowSessionMetrics({
    state: rtState,
    sessionPhase: phase,
    mode: status.mode,
  });

  return (
    <div className="home-market-live" aria-label="Thị trường trực tiếp">
      {banner && (
        <div className="live-status-banner" role="status">
          {banner}
        </div>
      )}
      {!data && conn !== "fallback" && <div className="skeleton" aria-busy="true" />}
      {!data && conn === "fallback" && (
        <div className="error-box" role="alert">
          Không tải được phân tích thị trường. Đang thử lại…
        </div>
      )}
      {data && <ConnStatus conn={conn} closed={phase === "closed"} lunch={phase === "lunch"} />}
      {data && (
        <>
          <IndexStrip index={data.index} asof={data.asof} />
          <BreadthBars breadth={data.breadth} />
          <MoversGrid lists={data.lists} profile={profile} showMetrics={showMetrics} />
          <SectorHeatmap heatmap={data.heatmap} profile={profile} showMetrics={showMetrics} />
          {data.disclaimer && (
            <p className="muted" style={{ fontSize: "var(--fs-xs)", maxWidth: "70ch" }}>
              {data.disclaimer}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ConnStatus({
  conn,
  closed,
  lunch,
}: {
  conn: MarketConn;
  closed: boolean;
  lunch: boolean;
}) {
  let text: string;
  let cls = "market-conn";
  if (lunch && conn !== "fallback") {
    text = "Nghỉ trưa — mở lại 13:00";
  } else if (conn === "live" && closed) {
    text = "Tạm dừng — ngoài giờ giao dịch";
  } else if (conn === "live") {
    text = "Trực tiếp";
    cls += " market-conn--live";
  } else if (conn === "fallback") {
    text = "Mất kết nối — đang dùng dữ liệu cập nhật mỗi 30 giây";
    cls += " market-conn--fallback";
  } else {
    text = "Đang kết nối…";
  }
  return (
    <p className={cls} role="status">
      <span className="market-conn-dot" aria-hidden />
      {text}
    </p>
  );
}

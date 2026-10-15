import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useLive } from "../live/LiveContext";
import { bannerForState, canShowSessionMetrics } from "../live/staleness";
import { BreadthBars } from "./BreadthBars";
import { IndexStrip } from "./IndexStrip";
import { MoversGrid } from "./MoversGrid";
import { SectorHeatmap } from "./SectorHeatmap";

export function HomeMarketDashboard({ profile = "long_term" }: { profile?: string }) {
  const { status } = useLive();
  const marketQ = useQuery({
    queryKey: ["realtime-market"],
    queryFn: () => api.realtimeMarket(),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const data = marketQ.data;
  const rtState = String(data?.realtime?.state || status.state || "no_realtime");
  const phase = status.sessionPhase ?? data?.session?.phase ?? null;
  const reason = status.reason ?? null;
  const banner =
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
      {marketQ.isLoading && <div className="skeleton" aria-busy="true" />}
      {marketQ.isError && (
        <div className="error-box" role="alert">
          Không tải được phân tích thị trường. Thử tải lại trang.
        </div>
      )}
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

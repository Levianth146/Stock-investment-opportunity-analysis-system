import { useEffect, useSyncExternalStore } from "react";
import { marketStream, type MarketSnapshot } from "./marketStream";

/** Đọc luồng thị trường; `active=true` giữ kết nối SSE mở khi component còn mount. */
export function useMarketStream(active = true): MarketSnapshot {
  useEffect(() => (active ? marketStream.retain() : undefined), [active]);
  return useSyncExternalStore(marketStream.subscribe, marketStream.getSnapshot);
}

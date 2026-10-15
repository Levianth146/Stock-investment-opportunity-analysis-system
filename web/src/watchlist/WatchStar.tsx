import { useEffect, useState } from "react";
import { isWatched, toggleWatch, WATCHLIST_MAX } from "./storage";
import { showToast } from "../toast";

export function WatchStar({ symbol }: { symbol: string }) {
  const [on, setOn] = useState(() => isWatched(symbol));

  useEffect(() => {
    setOn(isWatched(symbol));
  }, [symbol]);

  return (
    <button
      type="button"
      className={on ? "watch-star watch-star--on" : "watch-star"}
      aria-pressed={on}
      aria-label={on ? `Bỏ ${symbol} khỏi theo dõi` : `Thêm ${symbol} vào theo dõi`}
      title={on ? "Đang theo dõi" : "Theo dõi"}
      onClick={() => {
        const before = isWatched(symbol);
        const { symbols, added } = toggleWatch(symbol);
        const nowOn = symbols.includes(symbol.toUpperCase());
        setOn(nowOn);
        if (!before && !added && symbols.length >= WATCHLIST_MAX) {
          showToast(`Tối đa ${WATCHLIST_MAX} mã theo dõi.`);
        } else if (nowOn) {
          showToast(`Đã thêm ${symbol} vào theo dõi.`);
        } else {
          showToast(`Đã bỏ ${symbol} khỏi theo dõi.`);
        }
      }}
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
        <path
          d="M12 3.5l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.8 7.2 18.4l.9-5.4-3.9-3.8 5.4-.8L12 3.5z"
          fill={on ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="1.5"
        />
      </svg>
    </button>
  );
}

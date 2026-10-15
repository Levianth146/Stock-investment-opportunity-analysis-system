import {useEffect, useState} from 'react';
import type {PriceKind} from './staleness';
import {priceKind} from './staleness';

export interface LiveQuote {
  symbol: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume?: number | null;
  state?: string | null;
  basis?: string | null;
  label?: string | null;
  ts?: string | null;
}

const POLL_OPEN_MS = 8_000;
const POLL_CLOSED_MS = 30_000;

/**
 * Giá trực tiếp của một mã qua /api/quotes (poll). Không có luồng thật (thiếu khóa, ngoài giờ, lỗi)
 * thì trả null và giao diện dùng giá EOD từ snapshot.
 */
export function useQuote(symbol: string): {quote: LiveQuote | null; kind: PriceKind} {
  const [quote, setQuote] = useState<LiveQuote | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    setQuote(null);
    const tick = async () => {
      let next = POLL_CLOSED_MS;
      try {
        if (document.visibilityState !== 'hidden') {
          const r = await fetch(`/api/quotes?symbols=${encodeURIComponent(symbol)}`);
          if (r.ok) {
            const body = await r.json();
            const item = ((body.items || []) as LiveQuote[]).find(q => q.symbol === symbol) || null;
            if (!stopped) setQuote(item && item.price != null ? item : null);
            if (item?.state === 'live') next = POLL_OPEN_MS;
          }
        }
      } catch {
        /* giữ giá cũ */
      }
      if (!stopped) timer = window.setTimeout(tick, next);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [symbol]);
  return {quote, kind: priceKind(quote && {state: quote.state, basis: quote.basis, price: quote.price})};
}

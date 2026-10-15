/**
 * SSE shared — nhóm ≤20 mã/kết nối theo mã đang hiện.
 * Lỗi SSE → poll /api/quotes 15s; ẩn tab → tạm; hiện lại → khôi phục.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { LiveQuote, LiveStatus } from "./types";
import { bannerForState, resolveDisplayState } from "./staleness";

const MAX_PER_CONN = 20;
const POLL_MS = 15_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

interface LiveCtx {
  quotes: Record<string, LiveQuote>;
  status: LiveStatus;
  /** Đăng ký mã cần theo dõi (refcount). Trả hàm hủy. */
  watch: (symbols: string[]) => () => void;
  getQuote: (symbol: string) => LiveQuote | undefined;
}

const Ctx = createContext<LiveCtx | null>(null);

function chunkSymbols(syms: string[]): string[][] {
  const u = [...new Set(syms.map((s) => s.toUpperCase()).filter(Boolean))];
  const out: string[][] = [];
  for (let i = 0; i < u.length; i += MAX_PER_CONN) {
    out.push(u.slice(i, i + MAX_PER_CONN));
  }
  return out;
}

function applyItems(
  prev: Record<string, LiveQuote>,
  items: LiveQuote[],
  now: number,
): Record<string, LiveQuote> {
  const next = { ...prev };
  for (const it of items) {
    const sym = String(it.symbol || "").toUpperCase();
    if (!sym) continue;
    next[sym] = {
      ...it,
      symbol: sym,
      receivedAt: now,
      state: resolveDisplayState(
        { ...it, receivedAt: now },
        { now, sessionOpen: it.state !== "closed" },
      ),
    };
  }
  return next;
}

export function LiveProvider({ children }: { children: ReactNode }) {
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({});
  const [status, setStatus] = useState<LiveStatus>({
    mode: "unknown",
    state: "no_realtime",
    banner: null,
  });
  const refs = useRef<Map<string, number>>(new Map());
  const [, bump] = useState(0);
  const visible = useMemo(() => {
    const out: string[] = [];
    refs.current.forEach((n, s) => {
      if (n > 0) out.push(s);
    });
    return out.sort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bump]);

  const watch = useCallback((symbols: string[]) => {
    const clean = symbols.map((s) => s.toUpperCase()).filter(Boolean);
    for (const s of clean) {
      refs.current.set(s, (refs.current.get(s) || 0) + 1);
    }
    bump((x) => x + 1);
    return () => {
      for (const s of clean) {
        const n = (refs.current.get(s) || 1) - 1;
        if (n <= 0) refs.current.delete(s);
        else refs.current.set(s, n);
      }
      bump((x) => x + 1);
    };
  }, []);

  const getQuote = useCallback(
    (symbol: string) => quotes[symbol.toUpperCase()],
    [quotes],
  );

  // Stale ticker: quét mỗi 5s theo receive time
  useEffect(() => {
    const id = window.setInterval(() => {
      const now =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      setQuotes((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const [sym, q] of Object.entries(prev)) {
          const st = resolveDisplayState(q, {
            now,
            sessionOpen: q.state !== "closed" && q.state !== "no_realtime",
          });
          if (st !== q.state) {
            next[sym] = { ...q, state: st };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 5_000);
    return () => clearInterval(id);
  }, []);

  // Status hub
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch("/api/realtime/status");
        if (!r.ok) return;
        const body = await r.json();
        if (cancelled) return;
        const state = String(body.state || body.mode || "no_realtime");
        const phase = body.session?.phase;
        const reason =
          typeof body.reason === "string" ? body.reason : null;
        const displayState =
          state === "live" && phase === "closed" ? "closed" : state;
        setStatus({
          mode: String(body.mode || state),
          state,
          sessionPhase: phase,
          reason,
          banner:
            phase === "lunch" ? "Nghỉ trưa — HOSE mở lại lúc 13:00. Đang hiện giá phiên sáng." : bannerForState(displayState, null, reason),
        });
      } catch {
        /* offline */
      }
    };
    void load();
    const id = window.setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // SSE + poll fallback theo nhóm visible
  useEffect(() => {
    if (!visible.length) return;

    let stopped = false;
    let hidden = document.visibilityState === "hidden";
    const sources: EventSource[] = [];
    const pollTimers: number[] = [];
    let backoff = RECONNECT_BASE_MS;
    const reconnectTimers: number[] = [];

    const pollChunk = async (chunk: string[]) => {
      try {
        const r = await fetch(
          `/api/quotes?symbols=${encodeURIComponent(chunk.join(","))}`,
        );
        if (!r.ok) return;
        const body = await r.json();
        const items = (body.items || []) as LiveQuote[];
        const now =
          typeof performance !== "undefined" ? performance.now() : Date.now();
        setQuotes((prev) => applyItems(prev, items, now));
      } catch {
        /* ignore */
      }
    };

    const startPoll = (chunk: string[]) => {
      void pollChunk(chunk);
      const id = window.setInterval(() => {
        if (!hidden && !stopped) void pollChunk(chunk);
      }, POLL_MS);
      pollTimers.push(id);
    };

    const connectChunk = (chunk: string[]) => {
      if (stopped || hidden) {
        startPoll(chunk);
        return;
      }
      const url = `/api/stream?symbols=${encodeURIComponent(chunk.join(","))}`;
      let es: EventSource;
      try {
        es = new EventSource(url);
      } catch {
        startPoll(chunk);
        return;
      }
      sources.push(es);
      es.onmessage = (ev) => {
        backoff = RECONNECT_BASE_MS;
        try {
          const data = JSON.parse(ev.data) as {
            type?: string;
            items?: LiveQuote[];
          };
          if (data.type === "heartbeat" || !data.items) return;
          const now =
            typeof performance !== "undefined" ? performance.now() : Date.now();
          const items = data.items || [];
          setQuotes((prev) => applyItems(prev, items, now));
          // Chỉ tuyên bố live khi có tick thật (state live trên item) — không gắn "trực tiếp" sớm
          const anyLive = items.some((it) => it.state === "live");
          if (anyLive) {
            setStatus((s) => ({
              ...s,
              mode: "live",
              state: "live",
              banner: bannerForState("live"),
            }));
          }
        } catch {
          /* ignore bad frame */
        }
      };
      es.onerror = () => {
        es.close();
        const idx = sources.indexOf(es);
        if (idx >= 0) sources.splice(idx, 1);
        if (stopped || hidden) {
          startPoll(chunk);
          return;
        }
        startPoll(chunk);
        const wait = backoff;
        backoff = Math.min(backoff * 2, RECONNECT_MAX_MS);
        const t = window.setTimeout(() => {
          if (!stopped && !hidden) connectChunk(chunk);
        }, wait);
        reconnectTimers.push(t);
      };
    };

    for (const chunk of chunkSymbols(visible)) {
      connectChunk(chunk);
    }

    const onVis = () => {
      hidden = document.visibilityState === "hidden";
      if (hidden) {
        for (const es of sources) es.close();
        sources.length = 0;
      } else if (!stopped) {
        for (const id of pollTimers) clearInterval(id);
        pollTimers.length = 0;
        for (const chunk of chunkSymbols(visible)) {
          connectChunk(chunk);
        }
      }
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      stopped = true;
      document.removeEventListener("visibilitychange", onVis);
      for (const es of sources) es.close();
      for (const id of pollTimers) clearInterval(id);
      for (const t of reconnectTimers) clearTimeout(t);
    };
  }, [visible.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo(
    () => ({ quotes, status, watch, getQuote }),
    [quotes, status, watch, getQuote],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLive(): LiveCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLive phải nằm trong LiveProvider");
  return v;
}

export function useLiveQuotes(symbols: string[]): Record<string, LiveQuote> {
  const { watch, quotes } = useLive();
  const key = symbols.map((s) => s.toUpperCase()).sort().join(",");
  useEffect(() => {
    if (!key) return;
    return watch(key.split(",").filter(Boolean));
  }, [key, watch]);
  return useMemo(() => {
    const out: Record<string, LiveQuote> = {};
    for (const s of key.split(",").filter(Boolean)) {
      if (quotes[s]) out[s] = quotes[s]!;
    }
    return out;
  }, [key, quotes]);
}

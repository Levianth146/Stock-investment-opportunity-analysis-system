/** localStorage danh sách theo dõi — khóa có phiên bản, bỏ JSON hỏng. */

export const WATCHLIST_KEY = "stockai.watchlist.v1";
export const WATCHLIST_MAX = 50;

export interface WatchlistData {
  v: 1;
  symbols: string[];
  updatedAt: string;
}

function safeParse(raw: string | null): WatchlistData | null {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw) as unknown;
    if (!obj || typeof obj !== "object") return null;
    const o = obj as Record<string, unknown>;
    if (o.v !== 1 || !Array.isArray(o.symbols)) return null;
    const symbols = o.symbols
      .filter((s): s is string => typeof s === "string")
      .map((s) => s.toUpperCase().trim())
      .filter((s) => /^[A-Z0-9]{1,6}$/.test(s));
    return {
      v: 1,
      symbols: [...new Set(symbols)].slice(0, WATCHLIST_MAX),
      updatedAt: typeof o.updatedAt === "string" ? o.updatedAt : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function loadWatchlist(): string[] {
  try {
    const data = safeParse(localStorage.getItem(WATCHLIST_KEY));
    return data?.symbols ?? [];
  } catch {
    return [];
  }
}

export function saveWatchlist(symbols: string[]): string[] {
  const clean = [...new Set(symbols.map((s) => s.toUpperCase().trim()))]
    .filter((s) => /^[A-Z0-9]{1,6}$/.test(s))
    .slice(0, WATCHLIST_MAX);
  const payload: WatchlistData = {
    v: 1,
    symbols: clean,
    updatedAt: new Date().toISOString(),
  };
  try {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(payload));
  } catch {
    /* quota / private mode */
  }
  return clean;
}

export function toggleWatch(symbol: string): { symbols: string[]; added: boolean } {
  const sym = symbol.toUpperCase().trim();
  const cur = loadWatchlist();
  const has = cur.includes(sym);
  if (has) {
    return { symbols: saveWatchlist(cur.filter((s) => s !== sym)), added: false };
  }
  if (cur.length >= WATCHLIST_MAX) {
    return { symbols: cur, added: false };
  }
  return { symbols: saveWatchlist([...cur, sym]), added: true };
}

export function isWatched(symbol: string): boolean {
  return loadWatchlist().includes(symbol.toUpperCase());
}

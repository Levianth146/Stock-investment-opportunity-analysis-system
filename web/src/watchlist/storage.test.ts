import { beforeEach, describe, expect, it } from "vitest";
import {
  loadWatchlist,
  saveWatchlist,
  toggleWatch,
  WATCHLIST_KEY,
} from "./storage";

describe("watchlist storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("lưu và đọc", () => {
    saveWatchlist(["aaa", "BBB"]);
    expect(loadWatchlist()).toEqual(["AAA", "BBB"]);
  });

  it("bỏ JSON hỏng", () => {
    localStorage.setItem(WATCHLIST_KEY, "{not json");
    expect(loadWatchlist()).toEqual([]);
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify({ v: 99, symbols: ["X"] }));
    expect(loadWatchlist()).toEqual([]);
  });

  it("toggle thêm / bỏ", () => {
    expect(toggleWatch("VCB").added).toBe(true);
    expect(loadWatchlist()).toContain("VCB");
    expect(toggleWatch("VCB").added).toBe(false);
    expect(loadWatchlist()).not.toContain("VCB");
  });
});

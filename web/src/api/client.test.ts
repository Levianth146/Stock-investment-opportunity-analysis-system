import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("parse meta thành công", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers(),
        text: async () =>
          JSON.stringify({
            asof: "2026-10-08",
            disclaimer: "x",
            profiles: ["long_term", "swing"],
            default_profile: "long_term",
            universe_count: 1,
            scored_count: 1,
            formula: "v2",
          }),
      })),
    );
    const m = await api.meta();
    expect(m.asof).toBe("2026-10-08");
  });

  it("429 kèm Retry-After", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 429,
        headers: new Headers({ "Retry-After": "30" }),
        text: async () =>
          JSON.stringify({
            error: "Quá nhiều",
            asof: "2026-10-08",
            disclaimer: "x",
          }),
      })),
    );
    try {
      await api.meta();
      expect.fail("phải ném");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.status).toBe(429);
      expect(err.retryAfterSec).toBe(30);
    }
  });
});

import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { Profile } from "../api/types";

export type SignalFilter =
  | "above_ma50"
  | "above_ma200"
  | "rsi_ob"
  | "rsi_os"
  | "vol_up"
  | "low_risk";

const SIGNAL_KEYS: SignalFilter[] = [
  "above_ma50",
  "above_ma200",
  "rsi_ob",
  "rsi_os",
  "vol_up",
  "low_risk",
];

export function useRankingsUrlState() {
  const [sp, setSp] = useSearchParams();

  const state = useMemo(() => {
    const signals = new Set<SignalFilter>();
    const raw = sp.get("signals") || "";
    for (const part of raw.split(",")) {
      const p = part.trim() as SignalFilter;
      if (SIGNAL_KEYS.includes(p)) signals.add(p);
    }
    return {
      q: sp.get("q") || "",
      sector: sp.get("sector") || "",
      profile: (sp.get("profile") as Profile) || "long_term",
      sort: sp.get("sort") || "score",
      order: (sp.get("order") as "asc" | "desc") || "desc",
      signals,
    };
  }, [sp]);

  const patch = useCallback(
    (
      partial: Partial<Omit<typeof state, "signals">> & {
        signals?: Set<SignalFilter>;
      },
    ) => {
      const next = new URLSearchParams(sp);
      for (const [k, v] of Object.entries(partial)) {
        if (k === "signals") {
          const set = v as Set<SignalFilter> | undefined;
          if (!set || set.size === 0) next.delete("signals");
          else next.set("signals", [...set].join(","));
          continue;
        }
        if (v === undefined || v === null || v === "") next.delete(k);
        else next.set(k, String(v));
      }
      setSp(next, { replace: true });
    },
    [sp, setSp],
  );

  return { state, patch };
}

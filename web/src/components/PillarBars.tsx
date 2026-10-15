import type { RankingScores } from "../api/types";

const KEYS: (keyof RankingScores)[] = ["F", "T", "V", "S", "R"];
const LABELS: Record<string, string> = {
  F: "Cơ bản",
  T: "Kỹ thuật",
  V: "Định giá",
  S: "Tin tức",
  R: "Rủi ro",
};

export function PillarBars({ scores }: { scores: RankingScores }) {
  return (
    <div className="pillars" title={KEYS.map((k) => `${LABELS[k]}: ${scores[k] ?? "—"}`).join(" · ")}>
      {KEYS.map((k) => {
        const v = scores[k];
        const h = typeof v === "number" ? Math.max(2, Math.min(100, v)) : 2;
        return (
          <i
            key={k}
            style={{ height: `${h * 0.28}px`, opacity: v == null ? 0.3 : 1 }}
            aria-hidden
          />
        );
      })}
    </div>
  );
}

export { ratingClass } from "../ratings";

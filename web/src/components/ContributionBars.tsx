import type { RankingScores } from "../api/types";
import { num } from "../fmt";

const ORDER: (keyof RankingScores)[] = ["F", "T", "V", "S", "R"];

const META: Record<
  string,
  { label: string; meaning: string; subtract?: boolean }
> = {
  F: { label: "Cơ bản", meaning: "Cơ bản" },
  T: { label: "Kỹ thuật", meaning: "Kỹ thuật" },
  V: { label: "Định giá", meaning: "Định giá" },
  S: { label: "Tin tức", meaning: "Tin tức" },
  R: { label: "Rủi ro", meaning: "Rủi ro (trừ điểm)", subtract: true },
};

export function ContributionBars({ contrib }: { contrib: RankingScores }) {
  const vals = ORDER.map((k) => contrib[k]).filter(
    (v): v is number => typeof v === "number",
  );
  const maxAbs = Math.max(1, ...vals.map((v) => Math.abs(v)));

  return (
    <div className="contrib-bars" aria-label="Điểm đến từ đâu">
      {ORDER.map((k) => {
        const meta = META[k] ?? { label: k, meaning: k };
        const v = contrib[k];
        if (v == null) {
          return (
            <div className="bar-row" key={k}>
              <span className="bar-label" title={meta.meaning}>
                {meta.label}
              </span>
              <div className="track" />
              <span className="tabular muted bar-val">—</span>
            </div>
          );
        }
        const pctW = (Math.abs(v) / maxAbs) * 50;
        const pos = v >= 0;
        return (
          <div className="bar-row" key={k}>
            <span className="bar-label" title={meta.meaning}>
              {meta.label}
            </span>
            <div className="track">
              <div
                className="fill"
                style={{
                  left: pos ? "50%" : `${50 - pctW}%`,
                  width: `${pctW}%`,
                  background: pos ? "var(--contrib-pos)" : "var(--contrib-neg)",
                }}
              />
            </div>
            <span
              className={`tabular bar-val ${pos ? "pos" : "neg"}`}
              title={meta.meaning}
            >
              {v > 0 ? "+" : ""}
              {num(v, 2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

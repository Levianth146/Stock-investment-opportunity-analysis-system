/** Radar 5 trục: mã (accent) + trung vị ngành (xám). Nhãn trực tiếp, không chú giải. */

import type { RankingScores } from "../api/types";

const AXES: { key: keyof RankingScores | "safety"; label: string }[] = [
  { key: "F", label: "Cơ bản" },
  { key: "T", label: "Kỹ thuật" },
  { key: "V", label: "Định giá" },
  { key: "S", label: "Tin tức" },
  { key: "safety", label: "An toàn" },
];

export function radarPoints(
  values: number[],
  cx: number,
  cy: number,
  r: number,
): string {
  const n = values.length;
  return values
    .map((v, i) => {
      const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      const rr = (Math.max(0, Math.min(100, v)) / 100) * r;
      return `${cx + rr * Math.cos(ang)},${cy + rr * Math.sin(ang)}`;
    })
    .join(" ");
}

export function PillarRadar({
  scores,
  sectorMedian,
}: {
  scores: RankingScores | null | undefined;
  sectorMedian?: RankingScores | null;
}) {
  if (!scores) return null;
  const vals = AXES.map((a) => {
    if (a.key === "safety") {
      const r = scores.R;
      return typeof r === "number" ? 100 - r : 50;
    }
    const v = scores[a.key as keyof RankingScores];
    return typeof v === "number" ? v : 50;
  });
  const med = AXES.map((a) => {
    if (!sectorMedian) return 50;
    if (a.key === "safety") {
      const r = sectorMedian.R;
      return typeof r === "number" ? 100 - r : 50;
    }
    const v = sectorMedian[a.key as keyof RankingScores];
    return typeof v === "number" ? v : 50;
  });

  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const r = 72;
  const grid = [25, 50, 75, 100];

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      height={size}
      role="img"
      aria-label="Radar điểm thành phần"
      className="pillar-radar"
    >
      {grid.map((g) => (
        <polygon
          key={g}
          points={radarPoints(AXES.map(() => g), cx, cy, r)}
          fill="none"
          stroke="var(--rule)"
          strokeWidth="1"
        />
      ))}
      {AXES.map((a, i) => {
        const ang = -Math.PI / 2 + (i * 2 * Math.PI) / AXES.length;
        const x = cx + (r + 18) * Math.cos(ang);
        const y = cy + (r + 18) * Math.sin(ang);
        return (
          <text
            key={a.key}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="11"
            fill="var(--ink-2)"
          >
            {a.label}
          </text>
        );
      })}
      <polygon
        points={radarPoints(med, cx, cy, r)}
        fill="color-mix(in srgb, var(--ink-3) 18%, transparent)"
        stroke="var(--ink-3)"
        strokeWidth="1.5"
      />
      <polygon
        points={radarPoints(vals, cx, cy, r)}
        fill="color-mix(in srgb, var(--accent) 22%, transparent)"
        stroke="var(--accent)"
        strokeWidth="2"
      />
    </svg>
  );
}

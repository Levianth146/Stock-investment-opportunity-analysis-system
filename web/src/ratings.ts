/** Ngưỡng khuyến nghị 0–100 — mặc định khớp config/scoring.yaml. */

export interface RatingThreshold {
  min: number;
  label: string;
}

export const DEFAULT_RATINGS: RatingThreshold[] = [
  { min: 75, label: "Mua mạnh" },
  { min: 60, label: "Mua" },
  { min: 45, label: "Nắm giữ" },
  { min: 30, label: "Giảm tỷ trọng" },
  { min: 0, label: "Bán" },
];

/** Ngưỡng tăng dần > 0: 30, 45, 60, 75. */
export function thresholdMarks(ratings: RatingThreshold[] = DEFAULT_RATINGS): number[] {
  return ratings
    .map((r) => r.min)
    .filter((m) => m > 0)
    .sort((a, b) => a - b);
}

/** Nhãn vùng từ thấp tới cao (cùng thứ tự edges). */
export function zoneLabels(ratings: RatingThreshold[] = DEFAULT_RATINGS): string[] {
  return [...ratings].sort((a, b) => a.min - b.min).map((r) => r.label);
}

export function ratingsFromMeta(meta: {
  ratings?: RatingThreshold[] | null;
} | null | undefined): RatingThreshold[] {
  const rows = meta?.ratings;
  if (!Array.isArray(rows) || rows.length < 2) return DEFAULT_RATINGS;
  const ok = rows.every(
    (r) => r && typeof r.min === "number" && typeof r.label === "string",
  );
  return ok ? rows : DEFAULT_RATINGS;
}

export function ratingTone(
  rating: string,
): "strong-buy" | "buy" | "hold" | "reduce" | "sell" | "none" {
  const r = rating.toLowerCase();
  if (r.includes("mạnh") || r.includes("manh")) return "strong-buy";
  if (r.includes("mua")) return "buy";
  if (r.includes("giảm") || r.includes("giam")) return "reduce";
  if (r.includes("bán") || r.includes("ban")) return "sell";
  if (r.includes("nắm") || r.includes("nam") || r.includes("giữ") || r.includes("giu"))
    return "hold";
  return "none";
}

export function ratingClass(rating: string): string {
  const t = ratingTone(rating);
  if (t === "none") return "rating-hold";
  return `rating-${t}`;
}

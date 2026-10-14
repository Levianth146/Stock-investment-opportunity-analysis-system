/** Đọc token CSS theme cho lightweight-charts / SVG. */

export function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return v || fallback;
}

/** Grid ngang: ink-3 @ 15% opacity. */
export function gridLineColor(): string {
  const ink3 = cssVar("--ink-3", "#6b7882");
  // Fallback nếu trình duyệt không hỗ trợ color-mix trong canvas
  if (ink3.startsWith("#") && ink3.length === 7) {
    const r = parseInt(ink3.slice(1, 3), 16);
    const g = parseInt(ink3.slice(3, 5), 16);
    const b = parseInt(ink3.slice(5, 7), 16);
    return `rgba(${r},${g},${b},0.15)`;
  }
  return "rgba(107,120,130,0.15)";
}

export function chartColors() {
  return {
    ink: cssVar("--ink", "#11202b"),
    ink2: cssVar("--ink-2", "#52606b"),
    ink3: cssVar("--ink-3", "#6b7882"),
    rule: cssVar("--rule", "#d5dbe0"),
    accent: cssVar("--accent", "#0b6e87"),
    series1: cssVar("--series-1", "#0b82a0"),
    series2: cssVar("--series-2", "#eb6834"),
    series3: cssVar("--series-3", "#6250d6"),
    up: cssVar("--up", "#0b7a4b"),
    down: cssVar("--down", "#c62f2f"),
    paper: cssVar("--paper", "#f4f6f7"),
    grid: gridLineColor(),
  };
}

export function rebaseTo100(
  series: Array<{ time: string; close: number | null }>,
): Array<{ time: string; value: number }> {
  const first = series.find((p) => p.close != null && p.close > 0);
  if (!first || first.close == null) return [];
  const base = first.close;
  return series
    .filter((p) => p.close != null)
    .map((p) => ({
      time: p.time,
      value: (Number(p.close) / base) * 100,
    }));
}

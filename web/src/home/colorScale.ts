/**
 * Thang phân kỳ colorblind-safe cho % thay đổi.
 * Xanh dầu ↔ xám trung tính ↔ cam (không đỏ/xanh lá thuần).
 */

/** Nhãn số trên ô heatmap — làm tròn 1 chữ số. */
export function formatChangeLabel(pct: number | null | undefined): string {
  if (pct == null || Number.isNaN(pct)) return "";
  const s = pct >= 0 ? `+${pct.toFixed(1)}` : pct.toFixed(1);
  return s;
}

/**
 * Nội suy màu phân kỳ.
 * domain mặc định ±5%; clamp ngoài khoảng.
 */
export function changeToColor(
  pct: number | null | undefined,
  opts?: { dark?: boolean; maxAbs?: number },
): string {
  if (pct == null || Number.isNaN(pct)) {
    return opts?.dark ? "#26323b" : "#d5dbe0";
  }
  const maxAbs = opts?.maxAbs ?? 5;
  const t = Math.max(-1, Math.min(1, pct / maxAbs));
  // Colorblind-safe: xanh dầu #0B6E87 / trung tính / cam #C45C26
  const neg = opts?.dark ? [217, 89, 38] : [196, 92, 38]; // cam
  const mid = opts?.dark ? [38, 50, 59] : [213, 219, 224];
  const pos = opts?.dark ? [26, 155, 181] : [11, 110, 135]; // xanh dầu
  const from = t < 0 ? neg : mid;
  const to = t < 0 ? mid : pos;
  const u = t < 0 ? -t : t;
  const r = Math.round(from[0]! + (to[0]! - from[0]!) * u);
  const g = Math.round(from[1]! + (to[1]! - from[1]!) * u);
  const b = Math.round(from[2]! + (to[2]! - from[2]!) * u);
  // Khi t gần 0 dùng mid; khi |t| lớn nội suy mid→pos hoặc mid→neg
  if (t >= 0) {
    const rr = Math.round(mid[0]! + (pos[0]! - mid[0]!) * t);
    const gg = Math.round(mid[1]! + (pos[1]! - mid[1]!) * t);
    const bb = Math.round(mid[2]! + (pos[2]! - mid[2]!) * t);
    return `rgb(${rr},${gg},${bb})`;
  }
  const rr = Math.round(mid[0]! + (neg[0]! - mid[0]!) * -t);
  const gg = Math.round(mid[1]! + (neg[1]! - mid[1]!) * -t);
  const bb = Math.round(mid[2]! + (neg[2]! - mid[2]!) * -t);
  void r;
  void g;
  void b;
  return `rgb(${rr},${gg},${bb})`;
}

/** Chữ trên nền — ink nếu nền sáng, paper nếu nền tối (ước lượng luminance). */
export function labelInk(bg: string): string {
  const m = bg.match(/rgb\((\d+),(\d+),(\d+)\)/);
  if (!m) return "var(--ink)";
  const r = Number(m[1]);
  const g = Number(m[2]);
  const b = Number(m[3]);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.55 ? "#11202b" : "#e6edf2";
}

/** Quy tắc hiển thị giá tham chiếu theo ngành — không dùng lệch như upside. */

export const REF_UNRELIABLE_TIP =
  "Chênh lệch quá lớn, không đáng tin cậy";

export interface RefPriceView {
  /** Giá tham chiếu hiển thị (null → "—") */
  display: number | null;
  /** true khi |ref/price - 1| > 0.5 */
  unreliable: boolean;
  tooltip: string | null;
  /** (ref - price) / price dạng thập phân; null nếu không tính được / không tin cậy */
  deviation: number | null;
}

/**
 * Nếu thiếu giá hoặc tham chiếu → không hiển thị.
 * Nếu |ref/price - 1| > 0.5 → ẩn số, tooltip cảnh báo.
 */
export function evaluateRefPrice(
  price: number | null | undefined,
  ref: number | null | undefined,
): RefPriceView {
  if (
    price == null ||
    ref == null ||
    !Number.isFinite(price) ||
    !Number.isFinite(ref) ||
    price <= 0
  ) {
    return { display: null, unreliable: false, tooltip: null, deviation: null };
  }
  const ratio = ref / price - 1;
  if (Math.abs(ratio) > 0.5) {
    return {
      display: null,
      unreliable: true,
      tooltip: REF_UNRELIABLE_TIP,
      deviation: null,
    };
  }
  return {
    display: ref,
    unreliable: false,
    tooltip: null,
    deviation: ratio,
  };
}

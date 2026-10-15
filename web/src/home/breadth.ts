/** Độ rộng thị trường — 4 nhóm cộng đúng tổng liquid. */

export interface BreadthCounts {
  up: number;
  down: number;
  flat: number;
  unmatched: number;
}

export function breadthSum(b: BreadthCounts): number {
  return b.up + b.down + b.flat + b.unmatched;
}

export function normalizeBreadth(
  partial: Partial<BreadthCounts> & { liquid?: number },
): BreadthCounts {
  return {
    up: Number(partial.up) || 0,
    down: Number(partial.down) || 0,
    flat: Number(partial.flat) || 0,
    unmatched: Number(partial.unmatched) || 0,
  };
}

/** Kiểm tra 4 nhóm cộng = N (liquid). */
export function breadthCoversUniverse(b: BreadthCounts, liquid: number): boolean {
  return breadthSum(b) === liquid;
}

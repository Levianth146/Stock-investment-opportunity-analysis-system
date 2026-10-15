/** Squarified treemap (Bruls et al.) — diện tích tỷ lệ weight. */

export interface TreemapItem {
  id: string;
  weight: number;
  data?: unknown;
}

export interface TreemapRect {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  weight: number;
  data?: unknown;
}

function worst(row: number[], side: number): number {
  if (!row.length || side <= 0) return Infinity;
  const s = row.reduce((a, b) => a + b, 0);
  let maxR = 0;
  let minR = Infinity;
  for (const r of row) {
    maxR = Math.max(maxR, r);
    minR = Math.min(minR, r);
  }
  return Math.max((side * side * maxR) / (s * s), (s * s) / (side * side * minR));
}

/**
 * Squarify trong [0,width]×[0,height]. Weight ≤ 0 bỏ; tổng 0 → [].
 */
export function squarify(
  items: TreemapItem[],
  width: number,
  height: number,
): TreemapRect[] {
  const sorted = items
    .filter((i) => i.weight > 0 && Number.isFinite(i.weight))
    .sort((a, b) => b.weight - a.weight);
  const totalW = sorted.reduce((a, b) => a + b.weight, 0);
  if (!sorted.length || totalW <= 0 || width <= 0 || height <= 0) return [];

  const scale = (width * height) / totalW;
  const areas = sorted.map((i) => i.weight * scale);
  const result: TreemapRect[] = [];

  let x = 0;
  let y = 0;
  let w = width;
  let h = height;
  let i = 0;

  while (i < sorted.length) {
    const vertical = w >= h;
    const side = vertical ? h : w;
    const row: number[] = [];
    const rowIdx: number[] = [];

    while (i < sorted.length) {
      const next = areas[i]!;
      const trial = [...row, next];
      if (row.length && worst(trial, side) > worst(row, side)) break;
      row.push(next);
      rowIdx.push(i);
      i += 1;
    }

    const rowSum = row.reduce((a, b) => a + b, 0);
    if (vertical) {
      const rw = rowSum / h;
      let cy = y;
      for (let k = 0; k < row.length; k++) {
        const rh = row[k]! / rw;
        const it = sorted[rowIdx[k]!]!;
        result.push({
          id: it.id,
          x,
          y: cy,
          w: rw,
          h: rh,
          weight: it.weight,
          data: it.data,
        });
        cy += rh;
      }
      x += rw;
      w -= rw;
    } else {
      const rh = rowSum / w;
      let cx = x;
      for (let k = 0; k < row.length; k++) {
        const rw = row[k]! / rh;
        const it = sorted[rowIdx[k]!]!;
        result.push({
          id: it.id,
          x: cx,
          y,
          w: rw,
          h: rh,
          weight: it.weight,
          data: it.data,
        });
        cx += rw;
      }
      y += rh;
      h -= rh;
    }
  }
  return result;
}

export function areaSum(rects: TreemapRect[]): number {
  return rects.reduce((a, r) => a + Math.max(0, r.w) * Math.max(0, r.h), 0);
}

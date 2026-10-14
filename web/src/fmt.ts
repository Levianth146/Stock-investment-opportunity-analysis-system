/** Định dạng số / ngày kiểu Việt Nam (dấu chấm nghìn, phẩy thập phân). */

const nb = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const nb0 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
const nb1 = new Intl.NumberFormat("vi-VN", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (digits === 0) return nb0.format(v);
  if (digits === 1) return nb1.format(v);
  return new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(v);
}

export function pct(
  v: number | null | undefined,
  opts?: { alreadyPercent?: boolean; digits?: number },
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const alreadyPercent = opts?.alreadyPercent ?? false;
  const digits = opts?.digits ?? 1;
  const x = alreadyPercent ? v : v * 100;
  return `${num(x, digits)}%`;
}

/** % thay đổi phiên: null → "—"; kèm nhãn khi chưa có giá tham chiếu. */
export function changePctLabel(
  changePct: number | null | undefined,
  opts?: { prevCloseSource?: string | null; refLabel?: string | null },
): { text: string; note: string | null } {
  const missingRef =
    opts?.prevCloseSource === "none" ||
    opts?.refLabel === "chưa có giá tham chiếu";
  if (
    missingRef ||
    changePct === null ||
    changePct === undefined ||
    Number.isNaN(changePct)
  ) {
    return {
      text: "—",
      note: missingRef ? "chưa có giá tham chiếu" : null,
    };
  }
  const up = changePct >= 0;
  return {
    text: `${up ? "+" : ""}${num(changePct, 2)}%`,
    note: null,
  };
}

export function vnd(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return nb0.format(v);
}

export function score(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return num(v, 1);
}

export function ratio(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return num(v, digits);
}

export function dateVi(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

export function compactBillions(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${nb.format(v)} tỷ`;
}

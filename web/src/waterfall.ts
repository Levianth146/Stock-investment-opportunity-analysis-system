/** Cầu P&L phía client — cùng quy tắc với stockai.api.waterfall. */

export interface BridgeStep {
  label: string;
  value: number;
  kind: "absolute" | "delta";
}

export interface BridgeResult {
  start: number;
  end: number;
  steps: BridgeStep[];
  reconcile_ok: boolean;
}

function num(v: unknown): number | null {
  if (v == null) return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

export function buildIncomeBridge(
  items: Record<string, number | null | undefined> | null | undefined,
): BridgeResult | null {
  if (!items) return null;
  const rev = num(items.revenue);
  let nip = num(items.net_income_parent);
  if (nip == null) nip = num(items.net_income);
  if (rev == null || nip == null) return null;

  const gp = num(items.gross_profit);
  const selling = num(items.selling_expense);
  const admin = num(items.admin_expense);
  const ebit = num(items.ebit);
  const interest = num(items.interest_expense);
  const pretax = num(items.pretax_profit);

  let path: Array<[string, number]> = [["Doanh thu", rev]];
  if (gp != null) path.push(["LN gộp", gp]);
  if (ebit != null) path.push(["LN HĐ", ebit]);
  if (pretax != null) path.push(["LNTT", pretax]);
  path.push(["LNST CĐCT mẹ", nip]);

  const cleaned: Array<[string, number]> = [path[0]!];
  for (const [lab, val] of path.slice(1)) {
    if (Math.abs(val - cleaned[cleaned.length - 1]![1]) < 1e-12 && lab !== "LNST CĐCT mẹ") {
      continue;
    }
    cleaned.push([lab, val]);
  }
  path = cleaned;

  const steps: BridgeStep[] = [
    { label: path[0]![0], value: path[0]![1], kind: "absolute" },
  ];

  for (let i = 0; i < path.length - 1; i++) {
    const [aLab, aVal] = path[i]!;
    const [bLab, bVal] = path[i + 1]!;
    const needed = bVal - aVal;
    const comps: Array<[string, number]> = [];

    if (aLab === "Doanh thu" && bLab === "LN gộp") {
      comps.push(["Giá vốn", needed]);
    } else if ((aLab === "Doanh thu" || aLab === "LN gộp") && bLab === "LN HĐ") {
      let sga: number | null = null;
      if (selling != null || admin != null) sga = (selling || 0) + (admin || 0);
      if (sga != null && aLab === "LN gộp") {
        comps.push(["Chi phí BH+QL", -sga]);
        const residual = needed - -sga;
        if (Math.abs(residual) > 1e-9) comps.push(["Khác", residual]);
      } else {
        comps.push(["Khác", needed]);
      }
    } else if (bLab === "LNTT") {
      if (interest != null && aLab === "LN HĐ") {
        comps.push(["Lãi vay và khác", -interest]);
        const residual = needed - -interest;
        if (Math.abs(residual) > 1e-9) comps.push(["Khác", residual]);
      } else {
        comps.push(["Lãi vay và khác", needed]);
      }
    } else if (bLab === "LNST CĐCT mẹ") {
      comps.push(["Thuế và CĐTS", needed]);
    } else {
      comps.push(["Khác", needed]);
    }

    for (const [lab, val] of comps) {
      if (Math.abs(val) < 1e-12) continue;
      steps.push({ label: lab, value: val, kind: "delta" });
    }
    steps.push({ label: bLab, value: bVal, kind: "absolute" });
  }

  const merged: BridgeStep[] = [];
  for (const s of steps) {
    const last = merged[merged.length - 1];
    if (
      last &&
      s.label === "Khác" &&
      last.label === "Khác" &&
      s.kind === "delta" &&
      last.kind === "delta"
    ) {
      last.value += s.value;
    } else {
      merged.push({ ...s });
    }
  }

  let check = rev;
  for (const s of merged.slice(1)) {
    if (s.kind === "delta") check += s.value;
    else check = s.value;
  }

  return {
    start: rev,
    end: nip,
    steps: merged,
    reconcile_ok: Math.abs(check - nip) <= 1e-6,
  };
}

export function sumPeriodItems(
  periods: Array<{ items?: Record<string, number | null> }>,
  keys: string[],
): Record<string, number | null> {
  const acc: Record<string, number | null> = {};
  for (const k of keys) acc[k] = null;
  for (const p of periods) {
    const items = p.items || {};
    for (const k of keys) {
      const v = num(items[k]);
      if (v == null) continue;
      acc[k] = acc[k] == null ? v : (acc[k] as number) + v;
    }
  }
  return acc;
}

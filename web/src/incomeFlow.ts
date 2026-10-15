/** Luồng P&L Sankey — cùng quy tắc với stockai.api.income_flow (017c). */

export type FlowNodeKind =
  | "source"
  | "intermediate"
  | "sink"
  | "derived"
  | "loss"
  | "other_income";

export interface FlowNode {
  id: string;
  label: string;
  kind: FlowNodeKind;
  derived: boolean;
  value: number;
  pct_revenue: number | null;
}

export interface FlowLink {
  source: string;
  target: string;
  value: number;
  pct_revenue: number | null;
}

export interface IncomeFlowResult {
  revenue: number;
  npat: number;
  loss: boolean;
  nodes: FlowNode[];
  links: FlowLink[];
  notes: string[];
  conservation_ok: boolean;
  gross_margin: number | null;
  net_margin: number | null;
  expense_to_revenue: number | null;
}

const TOL_PCT = 0.005;

function num(v: unknown): number | null {
  if (v == null) return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function tol(magnitude: number): number {
  return Math.max(Math.abs(magnitude) * TOL_PCT, 1e-6);
}

function pctOf(value: number, revenue: number): number | null {
  if (Math.abs(revenue) < 1e-12) return null;
  return value / revenue;
}

function expenseRatio(
  items: Record<string, number | null | undefined>,
): number | null {
  const rev = num(items.revenue);
  if (rev == null || Math.abs(rev) < 1e-12) return null;
  const parts: number[] = [];
  for (const k of ["selling_expense", "admin_expense", "interest_expense"] as const) {
    const v = num(items[k]);
    if (v != null) parts.push(Math.abs(v));
  }
  if (!parts.length) return null;
  return parts.reduce((a, b) => a + b, 0) / Math.abs(rev);
}

function margins(
  items: Record<string, number | null | undefined>,
): { gm: number | null; nm: number | null } {
  const rev = num(items.revenue);
  const gp = num(items.gross_profit);
  let nip = num(items.net_income_parent);
  if (nip == null) nip = num(items.net_income);
  const gm =
    rev != null && Math.abs(rev) >= 1e-12 && gp != null ? gp / rev : null;
  const nm =
    rev != null && Math.abs(rev) >= 1e-12 && nip != null ? nip / rev : null;
  return { gm, nm };
}

/**
 * Kiểm tra bảo toàn: tại mỗi nút tổng vào ≈ tổng ra (sai số 0,5%).
 * Nguồn: out ≈ value; sink/loss/derived: in ≈ value.
 */
export function checkConservation(
  nodes: FlowNode[],
  links: FlowLink[],
): boolean {
  const inSum: Record<string, number> = {};
  const outSum: Record<string, number> = {};
  for (const n of nodes) {
    inSum[n.id] = 0;
    outSum[n.id] = 0;
  }
  for (const lk of links) {
    outSum[lk.source] = (outSum[lk.source] ?? 0) + lk.value;
    inSum[lk.target] = (inSum[lk.target] ?? 0) + lk.value;
  }
  for (const n of nodes) {
    const incoming = inSum[n.id] ?? 0;
    const outgoing = outSum[n.id] ?? 0;
    const val = n.value;
    if (n.kind === "source" || n.kind === "other_income") {
      if (Math.abs(outgoing - val) > tol(val)) return false;
    } else if (n.kind === "sink" || n.kind === "loss" || n.kind === "derived") {
      if (Math.abs(incoming - val) > tol(val)) return false;
      if (outgoing > tol(val)) return false;
    } else if (
      Math.abs(incoming - outgoing) > tol(Math.max(incoming, outgoing, val))
    ) {
      return false;
    }
  }
  return true;
}

export function buildIncomeFlow(
  items: Record<string, number | null | undefined> | null | undefined,
): IncomeFlowResult | null {
  if (!items) return null;
  const rev = num(items.revenue);
  let nip = num(items.net_income_parent);
  if (nip == null) nip = num(items.net_income);
  if (rev == null || nip == null) return null;

  const notes: string[] = [];
  const gp = num(items.gross_profit);
  const selling = num(items.selling_expense);
  const admin = num(items.admin_expense);
  const interest = num(items.interest_expense);
  const pretax = num(items.pretax_profit);
  let ni = num(items.net_income);

  if (selling == null) notes.push("Thiếu chi phí bán hàng — đã bỏ nút.");
  if (admin == null) notes.push("Thiếu chi phí quản lý — đã bỏ nút.");
  if (interest == null) notes.push("Thiếu chi phí lãi vay — đã bỏ nút.");

  let cit: number | null = null;
  if (pretax != null && ni != null) {
    cit = pretax - ni;
    if (cit < 0) {
      notes.push(
        "Thuế TNDN âm (hoàn/tín dụng) — gộp vào cân đối, không tách nút.",
      );
      cit = null;
    } else if (Math.abs(cit) < 1e-12) {
      cit = null;
    }
  } else {
    notes.push("Thiếu LNTT hoặc LNST — đã bỏ nút thuế TNDN.");
  }

  let minority: number | null = null;
  const nipRaw = num(items.net_income_parent);
  const niForMi = ni;
  if (niForMi != null && nipRaw != null) {
    minority = niForMi - nipRaw;
    if (minority < 0) {
      notes.push("Cổ đông thiểu số âm — gộp vào cân đối, không tách nút.");
      minority = null;
    } else if (Math.abs(minority) < 1e-12) {
      minority = null;
    }
  } else if (nipRaw == null && niForMi != null) {
    notes.push("Thiếu LNST cổ đông mẹ — dùng LNST tổng làm LNST mẹ.");
  } else {
    notes.push("Thiếu LNST hoặc LNST mẹ — đã bỏ nút cổ đông thiểu số.");
  }

  const nodes = new Map<string, FlowNode>();
  const links: FlowLink[] = [];

  const addNode = (
    id: string,
    label: string,
    kind: FlowNodeKind,
    derived = false,
  ) => {
    if (!nodes.has(id)) {
      nodes.set(id, {
        id,
        label,
        kind,
        derived,
        value: 0,
        pct_revenue: null,
      });
    }
  };

  const addLink = (source: string, target: string, value: number) => {
    if (value <= 1e-12) return;
    links.push({
      source,
      target,
      value,
      pct_revenue: null,
    });
  };

  addNode("revenue", "Doanh thu", "source");
  nodes.get("revenue")!.value = rev;

  let poolId = "revenue";
  if (gp == null) {
    notes.push("Thiếu lợi nhuận gộp — phân bổ chi phí từ doanh thu.");
  } else if (gp <= 0) {
    notes.push(
      "Lợi nhuận gộp ≤ 0 — không tách giá vốn/LN gộp; phân bổ từ doanh thu.",
    );
  } else {
    const cogs = rev - gp;
    addNode("gross_profit", "LN gộp", "intermediate");
    nodes.get("gross_profit")!.value = gp;
    if (cogs > tol(rev)) {
      addNode("cogs", "Giá vốn", "sink", true);
      nodes.get("cogs")!.value = cogs;
      addLink("revenue", "cogs", cogs);
      addLink("revenue", "gross_profit", gp);
    } else if (cogs < -tol(rev)) {
      addLink("revenue", "gross_profit", rev);
      const extra = gp - rev;
      addNode("other_income", "Thu nhập khác (ròng)", "other_income", true);
      nodes.get("other_income")!.value += extra;
      addLink("other_income", "gross_profit", extra);
      notes.push(
        "LN gộp lớn hơn doanh thu — bổ sung «Thu nhập khác (ròng)» (phái sinh).",
      );
    } else {
      addLink("revenue", "gross_profit", gp);
    }
    poolId = "gross_profit";
  }

  type Out = {
    id: string;
    label: string;
    value: number;
    kind: FlowNodeKind;
    derived: boolean;
  };
  const outflows: Out[] = [];

  if (selling != null && Math.abs(selling) > 1e-12) {
    outflows.push({
      id: "selling",
      label: "Chi phí bán hàng",
      value: Math.abs(selling),
      kind: "sink",
      derived: false,
    });
  }
  if (admin != null && Math.abs(admin) > 1e-12) {
    outflows.push({
      id: "admin",
      label: "Chi phí quản lý",
      value: Math.abs(admin),
      kind: "sink",
      derived: false,
    });
  }
  if (interest != null && Math.abs(interest) > 1e-12) {
    outflows.push({
      id: "interest",
      label: "Chi phí lãi vay",
      value: Math.abs(interest),
      kind: "sink",
      derived: false,
    });
  }
  if (cit != null && cit > 1e-12) {
    outflows.push({
      id: "cit",
      label: "Thuế TNDN",
      value: cit,
      kind: "sink",
      derived: true,
    });
  }
  if (minority != null && minority > 1e-12) {
    outflows.push({
      id: "minority",
      label: "Cổ đông thiểu số",
      value: minority,
      kind: "sink",
      derived: true,
    });
  }

  const lossCase = nip < 0;
  if (nip > 1e-12) {
    outflows.push({
      id: "npat",
      label: "LNST cổ đông mẹ",
      value: nip,
      kind: "sink",
      derived: false,
    });
  } else if (lossCase) {
    outflows.push({
      id: "loss",
      label: "Lỗ",
      value: Math.abs(nip),
      kind: "loss",
      derived: false,
    });
    notes.push(
      "LNST < 0: nút «Lỗ» (màu rủi ro); nếu chi phí vượt nguồn thì thêm «Thu nhập khác (ròng)» để mọi liên kết ≥ 0.",
    );
  } else {
    notes.push("LNST cổ đông mẹ ≈ 0 — không vẽ nút LNST.");
  }

  const accounted = outflows.reduce((a, o) => a + o.value, 0);
  const poolVal = nodes.get(poolId)!.value;
  const residual = poolVal - accounted;

  if (residual > tol(poolVal)) {
    outflows.push({
      id: "other_balance",
      label: "Khác (cân đối)",
      value: residual,
      kind: "derived",
      derived: true,
    });
    notes.push(
      "«Khác (cân đối)» là phần dư để bảo toàn luồng (phái sinh), không phải chỉ tiêu BCTC.",
    );
  } else if (residual < -tol(poolVal)) {
    const need = -residual;
    addNode("other_income", "Thu nhập khác (ròng)", "other_income", true);
    nodes.get("other_income")!.value += need;
    addLink("other_income", poolId, need);
    nodes.get(poolId)!.value += need;
    notes.push(
      "Chi phí/LN vượt nguồn có sẵn — thêm «Thu nhập khác (ròng)» (phái sinh) để mọi liên kết ≥ 0.",
    );
  }

  for (const o of outflows) {
    addNode(o.id, o.label, o.kind, o.derived);
    nodes.get(o.id)!.value = o.value;
    addLink(poolId, o.id, o.value);
  }

  const nodeList = [...nodes.values()].map((n) => ({
    ...n,
    pct_revenue: pctOf(n.value, rev),
  }));
  const linkList = links.map((lk) => ({
    ...lk,
    pct_revenue: pctOf(lk.value, rev),
  }));

  const { gm, nm } = margins(items);
  return {
    revenue: rev,
    npat: nip,
    loss: lossCase,
    nodes: nodeList,
    links: linkList,
    notes,
    conservation_ok: checkConservation(nodeList, linkList),
    gross_margin: gm,
    net_margin: nm,
    expense_to_revenue: expenseRatio(items),
  };
}

/** Phân tích cơ bản thuần: cơ cấu tài sản/nguồn vốn, tỷ số theo giá hiện tại, diễn giải. Đơn vị VND. */

export type Items = Record<string, number | null>;
export interface Period {
  period: string | number;
  items: Items;
  revenue_yoy?: number | null;
  net_income_yoy?: number | null;
}

export interface StructureQ {
  period: string | number;
  cash: number;
  inventory: number;
  otherCurrent: number;
  nonCurrentAssets: number;
  currentLiab: number;
  nonCurrentLiab: number;
  equity: number;
  totalAssets: number;
  debt: number | null;
}

const g = (it: Items, k: string): number | null => {
  const v = it[k];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
};

export function structureOf(p: Period): StructureQ | null {
  const ta = g(p.items, "total_assets");
  const eq = g(p.items, "total_equity");
  const tl = g(p.items, "total_liabilities");
  const ca = g(p.items, "current_assets");
  const cl = g(p.items, "current_liabilities");
  if (ta == null || ta <= 0 || eq == null || tl == null) return null;
  const cash = g(p.items, "cash") ?? 0;
  const inv = g(p.items, "inventory") ?? 0;
  const curA = ca ?? 0;
  const st = g(p.items, "short_term_debt");
  const lt = g(p.items, "long_term_debt");
  // Thiếu nợ ngắn hạn (hay gặp ở CTCK/ngân hàng): xấp xỉ bằng nợ vay ngắn hạn, không để 0% gây hiểu lầm.
  const curL = cl ?? Math.min(st ?? 0, tl);
  return {
    period: p.period,
    cash: Math.max(Math.min(cash, curA), 0),
    inventory: Math.max(inv, 0),
    otherCurrent: Math.max(curA - Math.min(cash, curA) - Math.max(inv, 0), 0),
    nonCurrentAssets: Math.max(ta - curA, 0),
    currentLiab: Math.max(curL, 0),
    nonCurrentLiab: Math.max(tl - curL, 0),
    equity: eq,
    totalAssets: ta,
    debt: st != null || lt != null ? (st ?? 0) + (lt ?? 0) : null,
  };
}

export interface Ratios {
  priceBasis: "live" | "eod";
  price: number | null;
  shares: number | null;
  marketCap: number | null;
  epsTtm: number | null;
  pe: number | null;
  bvps: number | null;
  pb: number | null;
  netIncomeTtm: number | null;
  revenueTtm: number | null;
  netMargin: number | null;
  roe: number | null;
  debtToEquity: number | null;
  liabToEquity: number | null;
  currentRatio: number | null;
  interestCover: number | null;
  revenueYoy: number | null;
  netIncomeYoy: number | null;
}

function sum4(rows: Period[], key: string): number | null {
  if (rows.length < 4) return null;
  let s = 0;
  for (const r of rows.slice(-4)) {
    const v = g(r.items, key);
    if (v == null) return null;
    s += v;
  }
  return s;
}

/** % tăng trưởng quý gần nhất so với cùng quý năm trước (cần ≥5 quý, đúng quý). */
function yoyQ(q: Period[], key: string): number | null {
  if (q.length < 5) return null;
  const a = q[q.length - 1]!;
  const b = q[q.length - 5]!;
  const qa = String(a.period).slice(-2);
  const qb = String(b.period).slice(-2);
  if (qa !== qb) return null;
  const x = g(a.items, key);
  const y = g(b.items, key);
  if (x == null || y == null || y <= 0) return null;
  return (x / y - 1) * 100;
}

export function ratiosOf(
  q: Period[],
  price: number | null,
  priceBasis: "live" | "eod",
  shares: number | null,
): Ratios {
  const last = q.length ? q[q.length - 1]! : null;
  const ni = sum4(q, "net_income_parent") ?? sum4(q, "net_income");
  const rev = sum4(q, "revenue");
  const eq = last ? g(last.items, "total_equity") : null;
  const tl = last ? g(last.items, "total_liabilities") : null;
  const st = last ? g(last.items, "short_term_debt") : null;
  const lt = last ? g(last.items, "long_term_debt") : null;
  const ca = last ? g(last.items, "current_assets") : null;
  const cl = last ? g(last.items, "current_liabilities") : null;
  const ebit = sum4(q, "ebit");
  const intr = sum4(q, "interest_expense");
  const epsSum = sum4(q, "eps");
  const epsTtm = epsSum ?? (ni != null && shares ? ni / shares : null);
  const bvps = eq != null && shares ? eq / shares : null;
  return {
    priceBasis,
    price,
    shares,
    marketCap: price != null && shares ? price * shares : null,
    epsTtm,
    pe: price != null && epsTtm != null && epsTtm > 0 ? price / epsTtm : null,
    bvps,
    pb: price != null && bvps != null && bvps > 0 ? price / bvps : null,
    netIncomeTtm: ni,
    revenueTtm: rev,
    netMargin: ni != null && rev ? (ni / rev) * 100 : null,
    roe: ni != null && eq ? (ni / eq) * 100 : null,
    debtToEquity: eq && (st != null || lt != null) ? ((st ?? 0) + (lt ?? 0)) / eq : null,
    liabToEquity: eq && tl != null ? tl / eq : null,
    currentRatio: ca != null && cl ? ca / cl : null,
    interestCover: ebit != null && intr ? ebit / Math.abs(intr) : null,
    revenueYoy: yoyQ(q, "revenue"),
    netIncomeYoy: yoyQ(q, "net_income_parent") ?? yoyQ(q, "net_income"),
  };
}

const t = (x: number, d = 1) => x.toLocaleString("vi-VN", { maximumFractionDigits: d });
const ty = (x: number) => `${t(x / 1e9, 0)} tỷ`;
const pc = (x: number) => `${x >= 0 ? "+" : ""}${t(x)}%`;

export interface Block {
  head: string;
  text: string;
}

export function narrateFundamental(opts: {
  s: StructureQ | null;
  prev: StructureQ | null;
  r: Ratios;
  sectorPe: number | null;
  sectorPb: number | null;
  isFinancial: boolean;
}): Block[] {
  const { s, prev, r, sectorPe, sectorPb, isFinancial } = opts;
  const out: Block[] = [];

  const val: string[] = [];
  if (r.marketCap != null) val.push(`Vốn hoá ${ty(r.marketCap)}${r.priceBasis === "live" ? " theo giá trực tiếp" : " theo giá đóng cửa"}.`);
  if (r.pe != null) {
    val.push(
      `P/E ${t(r.pe)}` +
        (sectorPe ? (r.pe < sectorPe * 0.85 ? `, thấp hơn trung vị ngành (${t(sectorPe)})` : r.pe > sectorPe * 1.15 ? `, cao hơn trung vị ngành (${t(sectorPe)})` : `, quanh trung vị ngành (${t(sectorPe)})`) : "") +
        ".",
    );
  } else if (r.epsTtm != null && r.epsTtm <= 0) val.push("Công ty đang lỗ trong 4 quý gần nhất nên P/E không có ý nghĩa.");
  if (r.pb != null) {
    val.push(
      `P/B ${t(r.pb, 2)}` +
        (sectorPb ? (r.pb < sectorPb * 0.85 ? `, thấp hơn trung vị ngành (${t(sectorPb, 2)})` : r.pb > sectorPb * 1.15 ? `, cao hơn trung vị ngành (${t(sectorPb, 2)})` : `, quanh trung vị ngành (${t(sectorPb, 2)})`) : "") +
        (r.pb < 1 ? "; giá thấp hơn giá trị sổ sách." : "."),
    );
  }
  if (r.roe != null && r.pb != null) val.push(`ROE ${t(r.roe)}% — P/B ${r.pb > 1.5 && r.roe < 10 ? "khá cao so với khả năng sinh lời" : r.pb < 1 && r.roe > 12 ? "thấp so với khả năng sinh lời" : "tương xứng tương đối với khả năng sinh lời"}.`);
  if (val.length) out.push({ head: "Quy mô và định giá", text: val.join(" ") });

  if (s && !isFinancial) {
    const shortShare = ((s.cash + s.inventory + s.otherCurrent) / s.totalAssets) * 100;
    const parts = [`Tài sản ngắn hạn chiếm ${t(shortShare, 0)}% tổng tài sản (${ty(s.totalAssets)}); tiền ${t((s.cash / s.totalAssets) * 100, 0)}%, hàng tồn kho ${t((s.inventory / s.totalAssets) * 100, 0)}%, tài sản dài hạn ${t((s.nonCurrentAssets / s.totalAssets) * 100, 0)}%.`];
    if (prev && prev.totalAssets > 0) parts.push(`Tổng tài sản ${pc((s.totalAssets / prev.totalAssets - 1) * 100)} so với quý trước.`);
    out.push({ head: "Cơ cấu tài sản", text: parts.join(" ") });
  }

  if (s) {
    const eqShare = (s.equity / s.totalAssets) * 100;
    const parts = [`Vốn chủ sở hữu ${t(eqShare, 0)}% nguồn vốn, nợ phải trả ${t(100 - eqShare, 0)}% (ngắn hạn ${t((s.currentLiab / s.totalAssets) * 100, 0)}%, dài hạn ${t((s.nonCurrentLiab / s.totalAssets) * 100, 0)}%).`];
    if (r.liabToEquity != null) parts.push(`Nợ phải trả/vốn CSH ${t(r.liabToEquity, 2)} lần${isFinancial ? " (đặc thù ngành tài chính nên đòn bẩy cao là bình thường)" : r.liabToEquity > 2 ? " — đòn bẩy cao" : r.liabToEquity < 1 ? " — đòn bẩy thấp" : ""}.`);
    if (!isFinancial && r.currentRatio != null) parts.push(`Thanh khoản hiện hành ${t(r.currentRatio, 2)} lần${r.currentRatio < 1 ? " (dưới 1: tài sản ngắn hạn không đủ trả nợ ngắn hạn)" : r.currentRatio > 2 ? " (rất thoải mái)" : ""}.`);
    if (!isFinancial && r.interestCover != null) parts.push(`Khả năng trả lãi (EBIT/lãi vay) ${t(r.interestCover, 1)} lần${r.interestCover < 2 ? " — mỏng" : ""}.`);
    out.push({ head: "Nguồn vốn và đòn bẩy", text: parts.join(" ") });
  }

  const eff: string[] = [];
  if (r.netMargin != null) eff.push(`Biên lợi nhuận ròng 4 quý ${t(r.netMargin)}%.`);
  if (r.roe != null) eff.push(`ROE (LNST 4 quý/vốn CSH quý gần nhất) ${t(r.roe)}%.`);
  if (r.revenueYoy != null) eff.push(`Doanh thu quý gần nhất ${pc(r.revenueYoy)} so với cùng kỳ.`);
  if (r.netIncomeYoy != null) eff.push(`Lợi nhuận ròng ${pc(r.netIncomeYoy)} so với cùng kỳ.`);
  if (eff.length) out.push({ head: "Hiệu quả và tăng trưởng", text: eff.join(" ") });

  out.push({
    head: "Lưu ý",
    text:
      "Báo cáo tài chính theo quý nên không thay đổi trong ngày; chỉ các tỷ số phụ thuộc giá (vốn hoá, P/E, P/B) cập nhật theo giá trực tiếp. Đây là mô tả số liệu, không phải khuyến nghị đầu tư.",
  });
  return out;
}

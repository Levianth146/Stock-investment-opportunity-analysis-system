/** Diễn giải kỹ thuật bằng tiếng Việt từ kết quả `analyze` — mô tả, không phải khuyến nghị đầu tư. */
import { VERDICT_VI, type TaResult } from "./indicators";

export interface NarrativeBlock {
  head: string;
  text: string;
}

const n0 = (x: number) => x.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const n1 = (x: number) => x.toLocaleString("vi-VN", { maximumFractionDigits: 1 });
const pctTxt = (x: number) => `${x >= 0 ? "+" : ""}${n1(x)}%`;

export function narrate(r: TaResult): NarrativeBlock[] {
  const out: NarrativeBlock[] = [];
  const { v, last } = r;

  // 1. Xu hướng
  const above = (m: number | null) => (m == null ? null : last >= m);
  const a20 = above(v.sma20);
  const a50 = above(v.sma50);
  const a200 = above(v.sma200);
  let trend: string;
  if (a20 && a50 && a200) trend = "Giá nằm trên cả MA20, MA50 và MA200: xu hướng tăng ở cả ngắn, trung và dài hạn.";
  else if (a20 === false && a50 === false && a200 === false) trend = "Giá nằm dưới cả MA20, MA50 và MA200: xu hướng giảm ở cả ngắn, trung và dài hạn.";
  else if (a200 === false && a20) trend = "Giá đã vượt MA20 nhưng vẫn dưới MA200: có nhịp hồi ngắn hạn trong xu hướng dài hạn còn yếu.";
  else if (a200 && a20 === false) trend = "Giá còn trên MA200 nhưng đã thủng MA20: điều chỉnh ngắn hạn trong xu hướng dài hạn tăng.";
  else trend = "Giá đang đan xen quanh các đường trung bình: xu hướng chưa rõ ràng.";
  if (v.cross === "golden") trend += " MA50 vừa cắt lên MA200 trong 10 phiên gần đây (golden cross).";
  if (v.cross === "death") trend += " MA50 vừa cắt xuống MA200 trong 10 phiên gần đây (death cross).";
  if (v.adx) trend += ` ADX ${n1(v.adx.adx)} — ${v.adx.adx > 25 ? "xu hướng đang mạnh" : "xu hướng yếu, thị trường đi ngang là chính"}.`;
  out.push({ head: "Xu hướng", text: trend });

  // 2. Động lượng
  const mom: string[] = [];
  if (v.rsi != null) {
    mom.push(
      v.rsi >= 70 ? `RSI ${n1(v.rsi)} ở vùng quá mua, nhịp tăng có thể chậm lại.`
        : v.rsi <= 30 ? `RSI ${n1(v.rsi)} ở vùng quá bán, áp lực bán đã lớn và dễ xuất hiện nhịp hồi.`
        : `RSI ${n1(v.rsi)} ở vùng trung tính (30–70).`,
    );
  }
  if (v.macd) {
    mom.push(
      v.macd.hist > 0 ? "MACD đang trên đường tín hiệu, động lượng nghiêng về phía tăng."
        : "MACD đang dưới đường tín hiệu, động lượng nghiêng về phía giảm.",
    );
  }
  if (v.stoch) mom.push(`Stochastic %K ${n1(v.stoch.k)}${v.stoch.k > 80 ? " (quá mua)" : v.stoch.k < 20 ? " (quá bán)" : ""}.`);
  if (mom.length) out.push({ head: "Động lượng", text: mom.join(" ") });

  // 3. Biến động
  const vol: string[] = [];
  if (v.bb) {
    vol.push(
      v.bb.pctB > 1 ? "Giá vượt dải Bollinger trên, biến động tăng mạnh."
        : v.bb.pctB < 0 ? "Giá thủng dải Bollinger dưới, biến động giảm mạnh."
        : `Giá nằm ở ${n0(v.bb.pctB * 100)}% bề rộng dải Bollinger; dải rộng ${n1(v.bb.widthPct)}% giá.`,
    );
  }
  if (v.atrPct != null) vol.push(`Biên độ dao động trung bình (ATR14) khoảng ${n1(v.atrPct)}% giá mỗi phiên.`);
  if (vol.length) out.push({ head: "Biến động", text: vol.join(" ") });

  // 4. Khối lượng
  const kl: string[] = [];
  if (v.volRatio != null) {
    kl.push(
      v.volRatio >= 2 ? `Khối lượng phiên hiện tại gấp ${n1(v.volRatio)} lần trung bình 20 phiên — dòng tiền tăng đột biến.`
        : v.volRatio >= 1.2 ? `Khối lượng cao hơn trung bình 20 phiên (${n1(v.volRatio)}×).`
        : v.volRatio <= 0.6 ? `Khối lượng thấp (${n1(v.volRatio)}× trung bình 20 phiên), sức xác nhận của biến động giá yếu.`
        : `Khối lượng quanh mức trung bình 20 phiên (${n1(v.volRatio)}×).`,
    );
  }
  if (v.obv != null) kl.push(v.obv > 0 ? "OBV 20 phiên tăng: dòng tiền ròng nghiêng về phía mua." : "OBV 20 phiên giảm: dòng tiền ròng nghiêng về phía bán.");
  if (kl.length) out.push({ head: "Khối lượng", text: kl.join(" ") });

  // 5. Hỗ trợ / kháng cự
  const sr: string[] = [];
  if (v.support20 != null && v.resist20 != null)
    sr.push(`Vùng hỗ trợ gần: ${n0(v.support20)} (đáy 20 phiên); kháng cự gần: ${n0(v.resist20)} (đỉnh 20 phiên).`);
  if (v.high52 != null && v.low52 != null && v.high52 > v.low52) {
    const pos = ((last - v.low52) / (v.high52 - v.low52)) * 100;
    sr.push(`Biên 52 tuần ${n0(v.low52)} – ${n0(v.high52)}; giá đang ở ${n0(pos)}% biên (${pctTxt((last / v.high52 - 1) * 100)} so với đỉnh).`);
  }
  if (sr.length) out.push({ head: "Hỗ trợ / kháng cự", text: sr.join(" ") });

  // 6. Tổng hợp
  const buy = r.rows.filter((x) => x.signal === "buy").length;
  const sell = r.rows.filter((x) => x.signal === "sell").length;
  out.push({
    head: "Tổng hợp",
    text:
      `${r.rows.length} chỉ báo: ${buy} nghiêng mua, ${sell} nghiêng bán, ${r.rows.length - buy - sell} trung tính → ` +
      `tín hiệu tổng hợp "${VERDICT_VI[r.all.verdict]}" ` +
      `(đường trung bình: ${VERDICT_VI[r.ma.verdict]}; dao động: ${VERDICT_VI[r.osc.verdict]}). ` +
      (r.ma.verdict !== r.osc.verdict && r.ma.score * r.osc.score < 0
        ? "Hai nhóm chỉ báo đang mâu thuẫn nhau nên độ tin cậy thấp. "
        : "") +
      "Đây là mô tả kỹ thuật dựa trên giá và khối lượng, không phải khuyến nghị mua bán.",
  });
  return out;
}

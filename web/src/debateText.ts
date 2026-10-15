/** Làm sạch chuỗi luận điểm từ API trước khi hiện trên web. */

/**
 * Bỏ tiền tố mẫu «Thêm dẫn chứng …:» — giữ phần metric phía sau nếu có.
 * Không đổi chuỗi nếu không khớp.
 */
export function stripDebatePadding(text: string): string {
  const t = (text || "").trim();
  if (!t) return t;
  const m = /^Thêm dẫn chứng[^:]*:\s*(.+)$/i.exec(t);
  if (m?.[1]) return m[1].trim();
  // Cả câu chỉ là lời kêu gọi thêm dẫn chứng → ẩn
  if (/^Thêm dẫn chứng/i.test(t)) return "";
  return t;
}

/** Token metric hay gặp trong câu luận điểm (để dedupe). */
const METRIC_TOKEN_RE =
  /\b(ROE|ROA|P\/E|P\/B|RSI|MACD|EPS|CFO|FCF|VaR|CVaR|beta|Biên gộp|Nợ\/VCSH|Tăng trưởng doanh thu|Tăng trưởng lợi nhuận)\b/gi;

function metricTokens(text: string): Set<string> {
  const out = new Set<string>();
  const m = text.match(METRIC_TOKEN_RE);
  if (m) {
    for (const t of m) out.add(t.toLowerCase());
  }
  // Số phần trăm / hệ số lặp lại cũng coi là dấu hiệu trùng
  const nums = text.match(/\d+[.,]\d+\s*%?/g);
  if (nums) {
    for (const n of nums.slice(0, 4)) out.add(`n:${n}`);
  }
  return out;
}

/**
 * Bỏ bullet trùng metric đã nêu ở dòng trước (cùng phía bull/bear).
 * Giữ dòng đầu tiên chứa mỗi cụm metric.
 */
export function dedupeDebateByMetrics(
  items: Array<{ text: string; refs?: string[] }>,
): Array<{ text: string; refs?: string[] }> {
  const seen = new Set<string>();
  const out: Array<{ text: string; refs?: string[] }> = [];
  for (const it of items) {
    const tokens = metricTokens(it.text);
    if (tokens.size === 0) {
      out.push(it);
      continue;
    }
    let dup = false;
    for (const t of tokens) {
      if (seen.has(t)) {
        dup = true;
        break;
      }
    }
    if (dup) continue;
    for (const t of tokens) seen.add(t);
    out.push(it);
  }
  return out;
}

export function cleanDebateItems(
  items: Array<{ text: string; refs?: string[] }> | null | undefined,
): Array<{ text: string; refs?: string[] }> {
  const stripped = (items || [])
    .map((it) => ({ ...it, text: stripDebatePadding(it.text) }))
    .filter((it) => it.text.length > 0);
  return dedupeDebateByMetrics(stripped);
}

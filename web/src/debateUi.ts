/** Nhãn nguồn / lỗi AI cho khối luận điểm — thuần, dễ unit test. */

export function debateSourceLabel(opts: {
  isCreating: boolean;
  source?: string | null;
  model?: string | null;
  createdAt?: string | null;
  asof?: string | null;
  formatWhen: (iso: string) => string;
}): string {
  if (opts.isCreating) return "Đang tạo bằng AI…";
  const src = String(opts.source || "").toUpperCase();
  if (src === "LLM" || src === "LIVE" || src === "CACHE") {
    const model = opts.model || "";
    const whenRaw = opts.createdAt || opts.asof;
    const when = whenRaw ? opts.formatWhen(String(whenRaw)) : "";
    return `AI${model ? ` · ${model}` : ""}${when ? ` · ${when}` : ""}`;
  }
  return "Tự động từ chỉ số — chưa dùng AI";
}

export function debateFailLine(opts: {
  isCreating: boolean;
  jobError: string | null;
  clickedAi: boolean;
  aiAttemptState?: string | null;
  reasonCode?: string | null;
  debateReason?: string | null;
  retryAfter?: number | null;
  viReason: (code: string, retryAfter?: number) => string | null;
}): string | null {
  if (opts.isCreating) return null;
  if (opts.jobError) return opts.jobError;
  if (!opts.clickedAi) return null;
  if (opts.aiAttemptState === "ok") return null;
  const code = String(opts.reasonCode || opts.debateReason || "");
  return opts.viReason(code, opts.retryAfter ?? undefined);
}

export function viJobFailReason(code: string, retryAfter?: number): string | null {
  if (!code) return "AI không tạo được lần này — đang hiện luận điểm từ chỉ số.";
  if (code === "circuit_open") {
    return retryAfter
      ? `AI tạm nghỉ do lỗi liên tiếp — thử lại sau khoảng ${retryAfter} giây.`
      : "AI tạm nghỉ do lỗi liên tiếp — thử lại sau ít phút.";
  }
  if (code === "quota_blocked" || code === "quota_or_missing_key") {
    return "Hết hạn mức AI hôm nay — dùng luận điểm từ chỉ số.";
  }
  if (code.includes("rate_limit") || code === "refresh_denied_no_budget") {
    return retryAfter
      ? `Đã hết lượt gọi AI — thử lại sau khoảng ${retryAfter} giây.`
      : "Đã hết lượt gọi AI trong giờ này — thử lại sau.";
  }
  if (
    code === "all_providers_failed" ||
    code === "llm_fallback_template" ||
    code.startsWith("llm_error")
  ) {
    return "AI không tạo được lần này — đang hiện luận điểm từ chỉ số.";
  }
  return "AI không tạo được lần này — đang hiện luận điểm từ chỉ số.";
}

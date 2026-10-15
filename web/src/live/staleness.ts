/** Staleness theo thời điểm nhận (receive), không so tick.ts với đồng hồ trình duyệt. */

export const DISPLAY_STALE_MS = 20_000;

/** Loại giá đang hiển thị: trực tiếp (trong phiên), chốt phiên hôm nay (tạm tính, chưa có EOD) hoặc EOD. */
export type PriceKind = "live" | "close" | "eod";
export function priceKind(
  q?: { state?: string | null; basis?: string | null; price?: number | null } | null,
): PriceKind {
  if (!q || q.price == null) return "eod";
  if (q.state === "live") return "live";
  if (q.basis === "close") return "close";
  return "eod";
}
export function priceKindWord(k: PriceKind): string {
  return k === "live" ? "giá trực tiếp" : k === "close" ? "giá chốt phiên hôm nay (tạm tính)" : "giá đóng cửa";
}

/**
 * Xác định state hiển thị từ quote + tuổi nhận.
 * `receivedAt` là performance.now() (hoặc Date.now() proxy) lúc client nhận tick.
 */
export function resolveDisplayState(
  quote: {
    state?: string | null;
    receivedAt?: number | null;
  },
  opts: {
    now?: number;
    sessionOpen?: boolean;
    staleAfterMs?: number;
  } = {},
): string {
  const base = quote.state || "closed";
  if (
    base === "closed" ||
    base === "no_realtime" ||
    base === "unit_mismatch"
  ) {
    return base;
  }
  const sessionOpen = opts.sessionOpen !== false;
  if (!sessionOpen) return "closed";
  if (base !== "live" && base !== "stale") return base;
  const recv = quote.receivedAt;
  if (recv == null || !Number.isFinite(recv)) return base;
  const now = opts.now ?? (typeof performance !== "undefined" ? performance.now() : Date.now());
  const limit = opts.staleAfterMs ?? DISPLAY_STALE_MS;
  if (now - recv > limit) return "stale";
  return "live";
}

/** Bản dịch ngắn tiếng Việt cho ``reason`` từ /api/realtime/status — không lộ secrets. */
export function reasonVi(reason: string | null | undefined): string | null {
  if (!reason) return null;
  if (reason === "disabled") return "Luồng giá trực tiếp đang tắt.";
  if (reason === "missing_key") return "Thiếu khóa kết nối giá — chưa có luồng trực tiếp.";
  if (reason === "sdk_missing") return "Thiếu thư viện kết nối sàn — chưa có giá trực tiếp.";
  if (reason === "no_ticks_yet") return "Đã kết nối nhưng chưa nhận tick giá.";
  if (reason === "no_ticks") return "Hơn 90 giây không nhận tick giá.";
  if (reason.startsWith("connect_error:")) {
    return "Không kết nối được luồng giá trực tiếp.";
  }
  return null;
}

export function bannerForState(
  state: string,
  closedDate?: string | null,
  reason?: string | null,
): string | null {
  switch (state) {
    case "live":
      return null; // nhãn nhỏ trên số, không banner lớn — chỉ khi đã có tick thật
    case "connecting": {
      const specific = reasonVi(reason);
      return specific
        ? `${specific} Đang dùng giá đóng cửa EOD.`
        : "Đang kết nối — chưa nhận tick giá. Đang dùng giá đóng cửa EOD.";
    }
    case "stale": {
      if (reason === "no_ticks" || reason === "no_ticks_yet") {
        const specific = reasonVi(reason);
        return specific
          ? `${specific} Đang dùng giá đóng cửa EOD.`
          : "Luồng giá chậm — đang dùng giá đóng cửa EOD.";
      }
      return "Giá tạm tính — cập nhật chậm (hơn 20 giây không có tick).";
    }
    case "closed":
      return closedDate
        ? `Đóng cửa ${closedDate}. Đang hiện giá phiên gần nhất.`
        : "Ngoài giờ giao dịch. Đang hiện giá đóng cửa.";
    case "no_realtime": {
      const specific = reasonVi(reason);
      return specific
        ? `${specific} Đang dùng giá đóng cửa EOD.`
        : "Không có luồng giá trực tiếp. Đang dùng giá đóng cửa EOD.";
    }
    case "unit_mismatch":
      return "Đơn vị giá lệch — đang dùng giá đóng cửa EOD.";
    default:
      return null;
  }
}

/**
 * Có hiện số % / Vol tương đối không.
 * Chỉ khi giá live (hoặc stale) hoặc phiên đóng hợp lệ — tránh "+0%" giả.
 */
export function canShowSessionMetrics(opts: {
  state?: string | null;
  sessionPhase?: string | null;
  mode?: string | null;
}): boolean {
  const st = opts.state || opts.mode || "";
  if (st === "live" || st === "stale") return true;
  if (st === "connecting" || st === "no_realtime") return false;
  if (st === "closed" || opts.sessionPhase === "closed") return true;
  return false;
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { priceKind, priceKindWord } from "../live/staleness";
import { dateVi, num } from "../fmt";
import { useLiveQuotes } from "../live/LiveContext";

const REASON_VI: Record<string, string> = {
  no_file: "Chưa chạy bước lấy cổ tức (scripts/fetch_dividends.py).",
  not_fetched: "Mã này chưa được lấy dữ liệu cổ tức.",
  no_events: "Nguồn không ghi nhận đợt chi trả cổ tức nào cho mã này.",
};

export function DividendHistory({ symbol, priceClose }: { symbol: string; priceClose: number | null }) {
  const q = useQuery({
    queryKey: ["dividends", symbol],
    queryFn: () => api.dividends(symbol),
    staleTime: 3_600_000,
  });
  const quote = useLiveQuotes([symbol])[symbol];
  const kind = priceKind(quote);
  const price = kind !== "eod" ? quote!.price! : priceClose;
  const d = q.data;
  if (q.isLoading) return <div className="skeleton" aria-busy="true" />;
  if (q.isError)
    return <p className="muted">Không tải được lịch sử cổ tức (API chưa cập nhật hoặc lỗi mạng). Khởi động lại API rồi tải lại trang.</p>;
  if (!d || !d.available)
    return <p className="muted">{REASON_VI[d?.reason || ""] || "Chưa có lịch sử cổ tức."}</p>;
  const yieldPct = d.dps_ttm_vnd && price ? (d.dps_ttm_vnd / price) * 100 : null;
  return (
    <section aria-label="Lịch sử chi trả cổ tức">
      <h3 className="ta-h" style={{ marginTop: 0 }}>Lịch sử chi trả</h3>
      <p className="muted ta-basis">
        {d.dps_ttm_vnd
          ? `Cổ tức tiền mặt 12 tháng gần nhất ${num(d.dps_ttm_vnd, 0)} đ/cp`
          : "Không có đợt chi trả tiền mặt trong 12 tháng gần nhất"}
        {yieldPct != null && ` → tỷ suất ${num(yieldPct, 2)}% theo ${priceKindWord(kind)}`}.
        Nguồn: {d.source}, lấy ngày {d.fetched_at ? dateVi(d.fetched_at) : "—"}.
      </p>
      <table className="ta-table">
        <thead>
          <tr><th scope="col">Ngày GDKHQ</th><th scope="col">Nội dung</th><th scope="col">Tỷ lệ</th><th scope="col">Đ/cp</th></tr>
        </thead>
        <tbody>
          {d.events.slice(0, 12).map((e, i) => (
            <tr key={`${e.ex_date}-${i}`}>
              <td className="tabular">{e.ex_date ? dateVi(e.ex_date) : "—"}</td>
              <td>{e.title || (e.kind === "stock" ? "Cổ phiếu" : "Tiền mặt")}</td>
              <td className="tabular">{e.percent_of_par != null ? `${num(e.percent_of_par, 1)}%` : "—"}</td>
              <td className="tabular">{e.dps_vnd != null ? num(e.dps_vnd, 0) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

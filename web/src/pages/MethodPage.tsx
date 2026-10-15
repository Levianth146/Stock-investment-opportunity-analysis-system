/** Phương pháp: công thức điểm, trọng số, ngưỡng và giới hạn — đọc từ /api/meta (config/scoring.yaml). */
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ratingsFromMeta } from "../ratings";

const PILLARS: Array<[string, string, string]> = [
  ["F", "Cơ bản (M2)", "ROE, tăng trưởng doanh thu/lợi nhuận, biên lợi nhuận, đòn bẩy, dòng tiền từ báo cáo tài chính."],
  ["T", "Kỹ thuật (M3)", "Xu hướng (MA20/50/200), động lượng (RSI, MACD), khối lượng, biến động (ATR) trên giá đóng cửa."],
  ["V", "Định giá (M4)", "P/E và P/B so với trung vị ngành; giá tham chiếu = bội số trung vị ngành × EPS/BVPS."],
  ["S", "Tin tức (M5)", "Cảm xúc tin tức gần đây; thiếu tin thì dùng điểm trung tính 50."],
  ["R", "Rủi ro (M6)", "Biến động, sụt giảm tối đa, VaR/CVaR, beta so với VN-Index. Điểm càng cao càng rủi ro."],
];

export function MethodPage() {
  const metaQ = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const m = metaQ.data;
  const sc = m?.scoring;
  const ratings = ratingsFromMeta(m);
  const profiles = sc?.profiles || {};
  const names: Record<string, string> = { long_term: "Dài hạn", swing: "Lướt sóng" };
  const rref = sc?.risk_reference ?? m?.risk_reference ?? 50;

  return (
    <div className="method-page">
      <h1 style={{ fontSize: "var(--fs-lg)" }}>Phương pháp chấm điểm</h1>
      <p className="muted" style={{ maxWidth: "64ch" }}>
        Mỗi mã được chấm trên 5 trụ cột rồi gộp thành điểm 0–100. Trọng số là giá trị minh họa,
        chưa được hiệu chỉnh hay kiểm định lại bằng dữ liệu lịch sử.
      </p>

      <h2 className="method-h">Công thức</h2>
      <pre className="method-formula tabular">
        {`Điểm = 50 + Σ wₖ·(Xₖ − 50) − λ_R·(R − ${rref})\nvới X ∈ {F, T, V, S}, giới hạn trong [0, 100]`}
      </pre>
      <p className="muted" style={{ maxWidth: "64ch" }}>
        Mức 50 là trung tính: trụ cột trên 50 cộng điểm, dưới 50 trừ điểm. Rủi ro R chỉ làm giảm
        điểm khi cao hơn mức tham chiếu {rref}.
      </p>

      <h2 className="method-h">Năm trụ cột</h2>
      <dl className="method-pillars">
        {PILLARS.map(([k, t, d]) => (
          <div key={k}>
            <dt>
              <strong>{k}</strong> · {t}
            </dt>
            <dd className="muted">{d}</dd>
          </div>
        ))}
      </dl>

      <h2 className="method-h">Trọng số theo hồ sơ</h2>
      {metaQ.isLoading && <p className="muted">Đang tải…</p>}
      {metaQ.isError && <p role="alert">Không tải được cấu hình chấm điểm.</p>}
      {Object.keys(profiles).length > 0 && (
        <div className="table-wrap">
          <table className="fin-table">
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>Hồ sơ</th>
                {["F", "T", "V", "S"].map((k) => (
                  <th key={k}>w{k}</th>
                ))}
                <th>λ_R</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(profiles).map(([k, p]) => (
                <tr key={k}>
                  <td style={{ textAlign: "left" }}>{names[k] || k}</td>
                  {["F", "T", "V", "S"].map((w) => (
                    <td key={w} className="tabular">
                      {Math.round((p.weights?.[w] ?? 0) * 100)}%
                    </td>
                  ))}
                  <td className="tabular">{p.lambda_R}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="method-h">Ngưỡng khuyến nghị</h2>
      <ul className="method-list">
        {ratings.map((r) => (
          <li key={r.label}>
            <span className="tabular">≥ {r.min}</span> — {r.label}
          </li>
        ))}
      </ul>

      <h2 className="method-h">Chốt chặn</h2>
      <ul className="method-list">
        {sc?.risk_gate && (
          <li>
            Rủi ro R ≥ {sc.risk_gate.R_threshold}: khuyến nghị tối đa “{sc.risk_gate.max_rating}”.
          </li>
        )}
        {sc?.data_gate?.limited_max_rating && (
          <li>
            Mã thanh khoản thấp (dữ liệu hạn chế): tối đa “{sc.data_gate.limited_max_rating}”.
          </li>
        )}
        {sc?.data_gate?.implausible_upside_pct != null && (
          <li>
            Giá tham chiếu cao hơn giá thị trường hơn {sc.data_gate.implausible_upside_pct}%: nghi
            lệch dữ liệu hoặc bẫy giá trị, tối đa “{sc.data_gate.implausible_max_rating}”.
          </li>
        )}
        {!sc && <li className="muted">—</li>}
      </ul>

      <h2 className="method-h">Giá trong phiên và điểm</h2>
      <p className="muted" style={{ maxWidth: "64ch" }}>
        Điểm và khuyến nghị tính trên dữ liệu cuối ngày (EOD) nên không đổi theo từng lệnh khớp.
        Giá, % thay đổi, khối lượng và chỉ số thị trường được cập nhật trực tiếp trong phiên; sau
        giờ đóng cửa hiển thị giá phiên gần nhất (tạm tính) cho đến khi dữ liệu cuối ngày về.
      </p>

      <h2 className="method-h">Giới hạn</h2>
      <ul className="method-list">
        <li>Giá tham chiếu là bội số trung vị ngành, không phải dự báo hay giá mục tiêu chắc chắn.</li>
        <li>Mã thiếu báo cáo năm hoặc thanh khoản thấp có điểm kém tin cậy hơn.</li>
        <li>Điểm xếp hạng mang tính hỗ trợ phân tích, không phải lời khuyên đầu tư.</li>
      </ul>
      {m?.asof && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Dữ liệu tính đến {m.asof} · công thức {m.formula}
        </p>
      )}
    </div>
  );
}

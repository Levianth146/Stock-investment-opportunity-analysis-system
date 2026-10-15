import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { dateVi, num } from "../fmt";
import { sectorVi } from "../sectors";

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${num(v * 100, 1)}%`;
}

/** Logo: ảnh cục bộ /logos/<MÃ>.(svg|png) nếu có, ngược lại ô chữ cái đầu mã. */
function Logo({ symbol }: { symbol: string }) {
  const [step, setStep] = useState(0);
  const exts = ["svg", "png"];
  if (step >= exts.length) {
    return (
      <span className="co-logo co-logo--letter" aria-hidden>
        {symbol.slice(0, 1)}
      </span>
    );
  }
  return (
    <img
      className="co-logo"
      src={`/logos/${symbol}.${exts[step]}`}
      alt=""
      width={56}
      height={56}
      onError={() => setStep((s) => s + 1)}
    />
  );
}

export function CompanyProfileCard({
  symbol,
  exchange,
  sector,
}: {
  symbol: string;
  exchange: string | null;
  sector: string | null;
}) {
  const q = useQuery({
    queryKey: ["company-profile", symbol],
    queryFn: () => api.companyProfile(symbol),
    staleTime: 3_600_000,
  });
  const [open, setOpen] = useState(false);
  const p = q.data?.profile;
  const intro = p?.intro || "";
  const long = intro.length > 380;

  return (
    <section className="co-profile" aria-label="Giới thiệu công ty">
      <div className="co-head">
        <Logo symbol={symbol} />
        <div>
          <h2 className="co-name">{p?.name || symbol}</h2>
          <p className="muted co-sub">
            {[exchange, sector ? sectorVi(sector) : null].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>
      {q.isLoading && <div className="skeleton" aria-busy="true" />}
      {q.isError && (
        <p className="muted">Không tải được hồ sơ công ty (API chưa cập nhật hoặc lỗi mạng). Khởi động lại API rồi tải lại trang.</p>
      )}
      {q.data && !q.data.available && (
        <p className="muted">Chưa có hồ sơ công ty cho mã này.</p>
      )}
      {p && (
        <>
          {intro && (
            <p className={`co-intro prose${long && !open ? " co-intro--clamp" : ""}`}>{intro}</p>
          )}
          {long && (
            <button type="button" className="link-btn" onClick={() => setOpen((v) => !v)}>
              {open ? "Thu gọn" : "Xem thêm"}
            </button>
          )}
          <dl className="co-facts">
            <div><dt>Niêm yết</dt><dd className="tabular">{p.listing_date ? dateVi(p.listing_date) : "—"}</dd></div>
            <div><dt>CP lưu hành</dt><dd className="tabular">{p.issue_share != null ? num(p.issue_share, 0) : "—"}</dd></div>
            <div><dt>Nhà nước</dt><dd className="tabular">{pct(p.state_pct)}</dd></div>
            <div><dt>Nước ngoài</dt><dd className="tabular">{pct(p.foreign_pct)}{p.foreign_max_pct != null ? ` / tối đa ${pct(p.foreign_max_pct)}` : ""}</dd></div>
            <div><dt>Free float</dt><dd className="tabular">{pct(p.free_float_pct)}</dd></div>
          </dl>
          <p className="muted co-note">
            Nguồn: {p.source}, hồ sơ cập nhật {p.data_date ? dateVi(p.data_date) : "—"}. Số liệu
            trong đoạn giới thiệu là kỳ báo cáo gần nhất, không phải dữ liệu trực tiếp.
          </p>
        </>
      )}
    </section>
  );
}

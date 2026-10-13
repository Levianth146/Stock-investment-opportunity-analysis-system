import React from 'react';
import { StockData } from '../data/stocks';

interface RisksAuditViewProps {
  stock: StockData;
}

export const RisksAuditView: React.FC<RisksAuditViewProps> = ({ stock }) => {
  return (
    <div className="space-y-4">
      {/* Banner */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#BA1A1A]">shield_lock</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Ma Trận Đánh Giá Rủi Ro & Chứng Thực Kiểm Toán ({stock.symbol})
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Hệ thống rà soát rủi ro tiền tệ, nợ vay ngân hàng, kiểm soát chất lượng BCTC và chỉ số Altman Z-Score.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-lg bg-[#E6F4EC] text-[#188253] border border-[#188253]/30 text-xs font-bold">
            Z-Score: 4.85 (Vùng An Toàn Tuyệt Đối)
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Risk Factors */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs space-y-3">
          <h3 className="text-sm font-bold text-[#0C1D2D] flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-[#BA1A1A]">warning</span>
            Các Yếu Tố Rủi Ro Được AI Nhận Diện
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="p-3 rounded-lg bg-[#FFF8F8] border border-[#FFDAD6]">
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-[#BA1A1A]">1. Rủi ro biến động tỷ giá Yên Nhật (JPY/VND)</span>
                <span className="font-semibold text-[#BA1A1A] bg-[#FFDAD6] px-2 py-0.5 rounded text-[10px]">
                  Mức độ: Trung bình - Cao
                </span>
              </div>
              <p className="text-[#44474E] leading-relaxed">
                Thị trường Nhật Bản đóng góp khoảng 38% tổng doanh thu xuất khẩu phần mềm. Việc JPY suy yếu có thể làm giảm biên lợi nhuận ròng khi quy đổi về VND khoảng 1.2 - 1.8%.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-[#FFF4D8] border border-[#B7791F]/30">
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-[#B7791F]">2. Áp lực cạnh tranh nhân lực CNTT chất lượng cao</span>
                <span className="font-semibold text-[#B7791F] bg-[#FFF4D8] px-2 py-0.5 rounded text-[10px]">
                  Mức độ: Trung bình
                </span>
              </div>
              <p className="text-[#44474E] leading-relaxed">
                Chi phí lương cho các kỹ sư trí tuệ nhân tạo (AI) và thiết kế vi mạch bán dẫn tăng trưởng nhanh, đòi hỏi biên lợi nhuận các hợp đồng ký mới phải duy trì ở mức cao.
              </p>
            </div>
          </div>
        </div>

        {/* Audit Certification Box */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-[#001735] flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-[#188253]">verified_user</span>
            Chứng Thực Kiểm Toán Độc Lập
          </h3>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-lg bg-[#EEF4FF] border border-[#C4C6CF]/40">
              <span className="text-[11px] text-[#68788C] block">Hãng kiểm toán độc lập:</span>
              <strong className="text-sm text-[#001735] font-bold block">{stock.audit.auditor}</strong>
              <span className="text-[11px] text-[#188253] font-semibold flex items-center gap-1 mt-1">
                <span className="material-symbols-outlined text-[14px]">check_circle</span>
                Ý kiến kiểm toán: Chấp thuận toàn phần không ngoại trừ
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between py-1 border-b border-[#E1E7EF]">
                <span className="text-[#68788C]">Kỳ BCTC:</span>
                <span className="font-semibold text-[#0C1D2D]">{stock.audit.period}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#E1E7EF]">
                <span className="text-[#68788C]">Nguồn gốc dữ liệu:</span>
                <span className="font-semibold text-[#0C1D2D]">{stock.audit.dataSource}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-[#68788C]">Mã xác thực SHA-256:</span>
                <span className="font-mono-numbers text-[11px] text-[#188253] font-bold">
                  {stock.audit.checksum}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

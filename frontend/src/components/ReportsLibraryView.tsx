import React from 'react';
import { CompanyLogo } from './CompanyLogo';

interface ReportsLibraryViewProps {
  onOpenPdfModal: () => void;
  onSelectStock: (symbol: string) => void;
}

export const ReportsLibraryView: React.FC<ReportsLibraryViewProps> = ({
  onOpenPdfModal,
  onSelectStock,
}) => {
  const reports = [
    {
      id: 1,
      symbol: 'FPT',
      title: 'Báo cáo Phân tích Chiến lược & Định giá DCF FPT Q3/2024',
      scope: 'Chuyên sâu (12 trang)',
      date: '24/10/2024',
      size: '4.2 MB',
      rating: 'MUA MẠNH',
      target: '172,800 đ (+24.8%)',
    },
    {
      id: 2,
      symbol: 'HPG',
      title: 'Kỳ vọng Chu kỳ Thép & Tiến độ Dự án Dung Quất 2',
      scope: 'Chuyên sâu (14 trang)',
      date: '22/10/2024',
      size: '5.1 MB',
      rating: 'MUA MẠNH',
      target: '37,500 đ (+29.8%)',
    },
    {
      id: 3,
      symbol: 'VNM',
      title: 'Báo cáo Phục hồi Biên Lợi Nhuận Gộp & Cổ tức Tiền mặt',
      scope: 'Tóm tắt điều hành (6 trang)',
      date: '18/10/2024',
      size: '2.8 MB',
      rating: 'MUA',
      target: '82,000 đ (+20.9%)',
    },
    {
      id: 4,
      symbol: 'MWG',
      title: 'Tái cơ cấu Bách Hóa Xanh & Tối ưu hóa Chuỗi Thế Giới Di Động',
      scope: 'Chuyên sâu (10 trang)',
      date: '15/10/2024',
      size: '3.9 MB',
      rating: 'MUA',
      target: '78,500 đ (+18.6%)',
    },
  ];

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">library_books</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Thư Viện Báo Cáo Phân Tích Định Lượng AI (StockLens Research)
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Các bản thẩm định tài chính độc lập được tự động cập nhật ngay sau khi doanh nghiệp công bố BCTC.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {reports.map((r) => (
          <div key={r.id} className="bg-white rounded-xl border border-[#E1E7EF] p-5 shadow-xs flex flex-col justify-between hover:border-[#1A56DB] transition-all">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <CompanyLogo symbol={r.symbol} size="md" />
                  <span className="px-2 py-0.5 rounded bg-[#EFF6FF] text-[#1A56DB] font-bold text-xs border border-[#BFDBFE]">
                    {r.symbol}
                  </span>
                </div>
                <span className="text-xs font-bold text-[#188253] bg-[#E6F4EC] px-2 py-0.5 rounded">
                  {r.rating}
                </span>
              </div>
              <h3 className="text-sm font-bold text-[#0C1D2D] mb-1.5 leading-snug">
                {r.title}
              </h3>
              <p className="text-xs text-[#68788C]">
                Quy mô: {r.scope} • Ngày xuất bản: {r.date} • Tệp: {r.size}
              </p>
              <div className="mt-3 p-2 bg-[#EFF6FF] rounded-lg text-xs flex justify-between border border-[#BFDBFE]/60">
                <span className="text-[#1A56DB] font-medium">Mục tiêu 12 tháng:</span>
                <strong className="text-[#0C1D2D] font-mono-numbers">{r.target}</strong>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-4 mt-4 border-t border-[#E1E7EF]">
              <button
                onClick={() => {
                  onSelectStock(r.symbol);
                  onOpenPdfModal();
                }}
                className="flex-1 py-2 px-3 bg-[#1A56DB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
              >
                <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
                Xem & Tải PDF
              </button>
              <button
                onClick={() => onSelectStock(r.symbol)}
                className="py-2 px-3 border border-[#BFDBFE] text-[#1A56DB] hover:bg-[#EFF6FF] rounded-lg text-xs font-semibold cursor-pointer"
              >
                Vào Dashboard
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

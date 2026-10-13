import React, { useState } from 'react';
import { StockData } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface StockHeaderProps {
  stock: StockData;
  isWatchlisted: boolean;
  onToggleWatchlist: () => void;
  onOpenCopilot: () => void;
  onOpenCompanyProfile: () => void;
}

export const StockHeader: React.FC<StockHeaderProps> = ({
  stock,
  isWatchlisted,
  onToggleWatchlist,
  onOpenCopilot,
  onOpenCompanyProfile,
}) => {
  const [copied, setCopied] = useState(false);

  const handleShare = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left: Brand / Stock identity & metrics */}
        <div className="flex items-start sm:items-center gap-3.5 min-w-0">
          {/* Corporate Official Logo */}
          <CompanyLogo symbol={stock.symbol} size="xl" className="flex-shrink-0" />
          
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-bold text-[#0C1D2D] tracking-tight">
                {stock.name}
              </h1>
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-[#EFF6FF] text-[#1A56DB] border border-[#BFDBFE]">
                {stock.exchange}: {stock.symbol}
              </span>
              <span className="text-xs text-[#68788C] font-medium hidden sm:inline">
                • {stock.industry}
              </span>
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold bg-[#E6F4EC] text-[#188253]">
                <span className="w-2 h-2 rounded-full bg-[#188253] animate-pulse"></span>
                Thị trường Đang mở cửa
              </span>
            </div>

            {/* Quick fundamental metrics row */}
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 mt-1.5 text-xs text-[#44474E]">
              <span>Vốn hóa: <strong className="text-[#0C1D2D] font-semibold">{stock.marketCap}</strong></span>
              <span className="text-[#C4C6CF]">•</span>
              <span>P/E TTM: <strong className="text-[#0C1D2D] font-semibold">{stock.pe}</strong></span>
              <span className="text-[#C4C6CF]">•</span>
              <span>P/B: <strong className="text-[#0C1D2D] font-semibold">{stock.pb}</strong></span>
              <span className="text-[#C4C6CF]">•</span>
              <span>ROE: <strong className="text-[#188253] font-semibold">{stock.roe}</strong></span>
              <span className="text-[#C4C6CF]">•</span>
              <span>Cổ tức TM: <strong className="text-[#0C1D2D] font-semibold">{stock.dividend}</strong></span>
              <span className="text-[#C4C6CF] hidden sm:inline">•</span>
              <span className="text-[#74777F] italic text-[11px] hidden sm:inline">
                Dữ liệu kiểm thử (Illustrative data)
              </span>
            </div>
          </div>
        </div>

        {/* Right Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          {/* Button: Mô tả sơ về doanh nghiệp */}
          <button
            onClick={onOpenCompanyProfile}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#EFF6FF] hover:bg-[#DBEAFE] text-[#1A56DB] border border-[#BFDBFE] text-xs font-bold transition-all shadow-xs cursor-pointer group"
            title="Xem hồ sơ, lịch sử hình thành và cơ cấu ngành của doanh nghiệp"
          >
            <span className="material-symbols-outlined text-[16px] text-[#1A56DB] group-hover:scale-110 transition-transform">
              info
            </span>
            <span>Mô tả doanh nghiệp</span>
          </button>

          <button
            onClick={onToggleWatchlist}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
              isWatchlisted
                ? 'bg-[#E6F4EC] border-[#188253]/30 text-[#188253]'
                : 'border-[#BFDBFE] text-[#1A56DB] hover:bg-[#EFF6FF]'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">
              {isWatchlisted ? 'check' : 'add'}
            </span>
            <span>{isWatchlisted ? 'Đã thêm Watchlist' : 'Thêm Watchlist'}</span>
          </button>

          <button
            onClick={handleShare}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E1E7EF] text-[#0C1D2D] hover:bg-[#EFF6FF] text-xs font-semibold transition-colors cursor-pointer relative"
          >
            <span className="material-symbols-outlined text-[16px]">share</span>
            <span>{copied ? 'Đã sao chép!' : 'Chia sẻ'}</span>
          </button>

          <button
            onClick={onOpenCopilot}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#F0E7FC] hover:bg-[#E4D4FA] text-[#6B46C1] border border-[#6B46C1]/30 text-xs font-bold transition-all shadow-xs cursor-pointer group"
          >
            <span className="material-symbols-outlined text-[16px] text-[#6B46C1] group-hover:scale-110 transition-transform">
              psychology
            </span>
            <span>AI Copilot</span>
          </button>
        </div>
      </div>
    </div>
  );
};

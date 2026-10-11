import React from 'react';
import { HOSE_MARKET_TICKERS } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface WatchlistViewProps {
  onSelectStock: (symbol: string) => void;
}

export const WatchlistView: React.FC<WatchlistViewProps> = ({ onSelectStock }) => {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">bookmark</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Danh Mục Theo Dõi Cá Nhân (Watchlist Chiến Lược 2024-2025)
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            12 cổ phiếu có điểm định lượng AI trên 75/100, biên an toàn &gt; 15% và thanh khoản cao.
          </p>
        </div>

        <button 
          onClick={() => alert('Đã đặt cảnh báo biến động giá ±2% cho toàn bộ 12 mã trong danh mục.')}
          className="px-3 py-1.5 rounded-lg bg-[#EFF6FF] hover:bg-[#DBEAFE] text-[#1A56DB] text-xs font-semibold flex items-center gap-1.5 self-start sm:self-auto cursor-pointer border border-[#BFDBFE]"
        >
          <span className="material-symbols-outlined text-[16px]">notifications_active</span>
          Bật cảnh báo toàn bộ
        </button>
      </div>

      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs overflow-x-auto custom-scrollbar">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#EFF6FF] text-[#1A56DB] font-semibold border-b border-[#BFDBFE]">
            <tr>
              <th className="py-2.5 px-3">Doanh nghiệp</th>
              <th className="py-2.5 px-3">Mã CP</th>
              <th className="py-2.5 px-3 text-right">Thị giá</th>
              <th className="py-2.5 px-3 text-right">Biến động</th>
              <th className="py-2.5 px-3 text-right">Khối lượng</th>
              <th className="py-2.5 px-3 text-center">Khuyến nghị AI</th>
              <th className="py-2.5 px-3 text-center">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E1E7EF] font-mono-numbers">
            {HOSE_MARKET_TICKERS.map((t) => (
              <tr 
                key={t.symbol}
                onClick={() => onSelectStock(t.symbol)}
                className="hover:bg-[#EFF6FF]/50 cursor-pointer transition-colors"
              >
                <td className="py-2.5 px-3 text-[#0C1D2D] font-sans font-bold flex items-center gap-2.5">
                  <CompanyLogo symbol={t.symbol} size="sm" className="flex-shrink-0" />
                  <span>{t.name}</span>
                </td>
                <td className="py-2.5 px-3 font-bold text-[#1A56DB] font-sans">
                  <span className="px-2 py-0.5 rounded bg-[#EFF6FF] border border-[#BFDBFE]">
                    {t.symbol}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-right font-bold text-[#0C1D2D]">
                  {t.match.toFixed(1)}k
                </td>
                <td className={`py-2.5 px-3 text-right font-bold ${t.change >= 0 ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                  {t.change >= 0 ? `+${t.pct.toFixed(2)}%` : `${t.pct.toFixed(2)}%`}
                </td>
                <td className="py-2.5 px-3 text-right text-[#0C1D2D]">
                  {(t.vol / 1000).toLocaleString('vi-VN')}k
                </td>
                <td className="py-2.5 px-3 text-center font-sans">
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#E6F4EC] text-[#188253]">
                    MUA MẠNH
                  </span>
                </td>
                <td className="py-2.5 px-3 text-center font-sans">
                  <button className="text-[#1A56DB] hover:text-[#1D4ED8] font-bold text-xs">
                    Chi tiết →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

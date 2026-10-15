import React from 'react';
import { HOSE_MARKET_TICKERS } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface HoseBoardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectStock: (symbol: string) => void;
  currentSymbol: string;
}

export const HoseBoardModal: React.FC<HoseBoardModalProps> = ({
  isOpen,
  onClose,
  onSelectStock,
  currentSymbol,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 select-none animate-in fade-in duration-150">
      <div 
        onClick={onClose}
        className="absolute inset-0 bg-[#001735]/40 backdrop-blur-xs cursor-pointer"
      ></div>

      <div className="relative w-full max-w-6xl max-h-[90vh] bg-white rounded-xl shadow-2xl border border-[#E1E7EF] flex flex-col overflow-hidden z-20">
        {/* Header */}
        <div className="px-5 py-3.5 bg-white border-b border-[#E1E7EF] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#1A56DB] text-white flex items-center justify-center">
              <span className="material-symbols-outlined text-[18px]">query_stats</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[#0C1D2D]">Bảng Điện Tử Thị Trường HOSE (Live Stream)</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#E6F4EC] text-[#188253]">
                  ● Khớp lệnh liên tục
                </span>
              </div>
              <p className="text-xs text-[#68788C]">
                VN-INDEX: <strong className="text-[#188253] font-mono-numbers">1,288.42 (+9.56 / +0.75%)</strong> • VN30: <strong className="text-[#188253] font-mono-numbers">1,354.12 (+11.20 / +0.83%)</strong>
              </p>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[#68788C] hover:text-[#1A56DB] hover:bg-[#EFF6FF] cursor-pointer"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Board Table */}
        <div className="flex-1 overflow-auto custom-scrollbar p-4">
          <table className="w-full text-xs text-left">
            <thead className="bg-[#EFF6FF] text-[#1A56DB] font-semibold sticky top-0 shadow-xs border-b border-[#BFDBFE]">
              <tr>
                <th className="py-2.5 px-3">Doanh Nghiệp & Logo</th>
                <th className="py-2.5 px-2">Mã CK</th>
                <th className="py-2.5 px-2 text-right">Trần</th>
                <th className="py-2.5 px-2 text-right">Sàn</th>
                <th className="py-2.5 px-2 text-right">TC</th>
                <th className="py-2.5 px-3 text-right bg-[#DBEAFE]/40 font-bold text-[#1E40AF]">Khớp Lệnh</th>
                <th className="py-2.5 px-2 text-right font-bold">+/-</th>
                <th className="py-2.5 px-2 text-right font-bold">%</th>
                <th className="py-2.5 px-3 text-right">Tổng KL</th>
                <th className="py-2.5 px-3 text-right">Khối Ngoại (Tỷ)</th>
                <th className="py-2.5 px-3 text-center">Hành động</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E1E7EF] font-mono-numbers">
              {HOSE_MARKET_TICKERS.map((t) => {
                const isSelected = currentSymbol === t.symbol;
                const isUp = t.change >= 0;

                return (
                  <tr 
                    key={t.symbol} 
                    onClick={() => { onSelectStock(t.symbol); onClose(); }}
                    className={`hover:bg-[#EFF6FF]/60 transition-colors cursor-pointer ${
                      isSelected ? 'bg-[#EFF6FF]' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 font-bold text-[#0C1D2D] font-sans flex items-center gap-2">
                      <CompanyLogo symbol={t.symbol} size="sm" className="flex-shrink-0" />
                      <span className="truncate max-w-[150px]">{t.name}</span>
                    </td>
                    <td className="py-2.5 px-2 font-bold font-sans">
                      <span className="inline-block px-1.5 py-0.5 rounded bg-[#EFF6FF] text-[#1A56DB] border border-[#BFDBFE]">
                        {t.symbol}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-right text-[#9333EA]">{t.ceil.toFixed(1)}</td>
                    <td className="py-2.5 px-2 text-right text-[#0284C7]">{t.floor.toFixed(1)}</td>
                    <td className="py-2.5 px-2 text-right text-[#D97706]">{t.ref.toFixed(1)}</td>
                    <td className={`py-2.5 px-3 text-right font-bold text-sm bg-[#EFF6FF]/50 ${isUp ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                      {t.match.toFixed(1)}
                    </td>
                    <td className={`py-2.5 px-2 text-right font-semibold ${isUp ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                      {isUp ? `+${t.change.toFixed(2)}` : t.change.toFixed(2)}
                    </td>
                    <td className={`py-2.5 px-2 text-right font-bold ${isUp ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                      {isUp ? `+${t.pct.toFixed(2)}%` : `${t.pct.toFixed(2)}%`}
                    </td>
                    <td className="py-2.5 px-3 text-right text-[#0C1D2D]">
                      {(t.vol / 1000).toLocaleString('vi-VN')}
                    </td>
                    <td className={`py-2.5 px-3 text-right font-semibold ${t.foreign > 0 ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                      {t.foreign > 0 ? `+${t.foreign}` : t.foreign}
                    </td>
                    <td className="py-2.5 px-3 text-center font-sans">
                      <button
                        className="px-2.5 py-1 text-[11px] font-semibold bg-[#1A56DB] hover:bg-[#1D4ED8] text-white rounded transition-colors shadow-xs"
                      >
                        Mở Báo Cáo
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

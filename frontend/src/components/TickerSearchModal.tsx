import React, { useState, useEffect } from 'react';
import { HOSE_MARKET_TICKERS } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface TickerSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectStock: (symbol: string) => void;
}

export const TickerSearchModal: React.FC<TickerSearchModalProps> = ({
  isOpen,
  onClose,
  onSelectStock,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = HOSE_MARKET_TICKERS.filter(
    (t) =>
      t.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 select-none animate-in fade-in duration-150">
      <div 
        onClick={onClose}
        className="absolute inset-0 bg-[#001735]/40 backdrop-blur-xs cursor-pointer"
      ></div>

      <div className="relative w-full max-w-xl bg-white rounded-xl shadow-2xl border border-[#BFDBFE] flex flex-col overflow-hidden z-20">
        {/* Search Input Bar */}
        <div className="p-3.5 border-b border-[#E1E7EF] flex items-center gap-2.5 bg-[#EFF6FF]/40">
          <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">search</span>
          <input
            autoFocus
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Tìm kiếm mã cổ phiếu, tên doanh nghiệp (FPT, HPG, VNM, VCB...)"
            className="flex-1 text-sm bg-transparent border-none focus:outline-none text-[#0C1D2D] placeholder:text-[#68788C]"
          />
          <span className="text-[10px] text-[#1A56DB] bg-white px-1.5 py-0.5 rounded border border-[#BFDBFE]">
            ESC để đóng
          </span>
        </div>

        {/* Results list */}
        <div className="max-h-80 overflow-y-auto custom-scrollbar p-2 divide-y divide-[#E1E7EF]/60">
          {filtered.length > 0 ? (
            filtered.map((t) => (
              <div
                key={t.symbol}
                onClick={() => {
                  onSelectStock(t.symbol);
                  onClose();
                }}
                className="p-2.5 rounded-lg hover:bg-[#EFF6FF] flex items-center justify-between transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-3">
                  <CompanyLogo symbol={t.symbol} size="md" className="flex-shrink-0" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-xs text-[#1A56DB]">{t.symbol}</span>
                      <span className="text-xs font-semibold text-[#0C1D2D] truncate max-w-[200px]">{t.name}</span>
                    </div>
                    <p className="text-[11px] text-[#68788C]">HOSE • Khối lượng: {(t.vol / 1000).toLocaleString('vi-VN')}k</p>
                  </div>
                </div>

                <div className="text-right font-mono-numbers">
                  <div className="text-xs font-bold text-[#0C1D2D]">{t.match.toFixed(1)}k</div>
                  <div className={`text-[11px] font-semibold ${t.change >= 0 ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                    {t.change >= 0 ? `+${t.pct.toFixed(2)}%` : `${t.pct.toFixed(2)}%`}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="p-6 text-center text-xs text-[#68788C]">
              Không tìm thấy mã cổ phiếu phù hợp.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

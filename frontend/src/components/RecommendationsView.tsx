import React from 'react';
import { HOSE_MARKET_TICKERS } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface RecommendationsViewProps {
  onSelectStock: (symbol: string) => void;
}

export const RecommendationsView: React.FC<RecommendationsViewProps> = ({ onSelectStock }) => {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">auto_awesome</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Danh Mục Khuyến Nghị Đầu Tư AI Quantitative Model 4.2
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Lọc tự động dựa trên 5 nhân tố F-T-V-S-R, biên an toàn &gt; 18%, tỷ lệ Sharpe tối ưu danh mục.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-lg bg-[#1A56DB] text-white text-xs font-bold font-mono-numbers shadow-xs">
            Hiệu suất mô hình YTD: +36.4% vs VNINDEX (+14.2%)
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {HOSE_MARKET_TICKERS.slice(0, 6).map((t, idx) => (
          <div 
            key={t.symbol}
            onClick={() => onSelectStock(t.symbol)}
            className="bg-white rounded-xl border border-[#E1E7EF] p-4.5 shadow-xs hover:border-[#1A56DB] hover:shadow-md transition-all cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <CompanyLogo symbol={t.symbol} size="md" />
                  <span className="font-bold text-sm text-[#1A56DB]">{t.symbol}</span>
                </div>
                <span className="text-xs font-bold text-[#188253] bg-[#E6F4EC] px-2 py-0.5 rounded">
                  {idx % 2 === 0 ? 'MUA MẠNH' : 'MUA'}
                </span>
              </div>
              <h3 className="text-xs font-bold text-[#0C1D2D] mb-1">{t.name}</h3>
              <div className="flex items-baseline gap-2 my-2 font-mono-numbers">
                <span className="text-lg font-extrabold text-[#0C1D2D]">{t.match.toFixed(1)}k</span>
                <span className={`text-xs font-bold ${t.change >= 0 ? 'text-[#188253]' : 'text-[#C04B4B]'}`}>
                  {t.change >= 0 ? `+${t.pct.toFixed(2)}%` : `${t.pct.toFixed(2)}%`}
                </span>
              </div>
              <p className="text-[11px] text-[#68788C] line-clamp-2">
                Tăng trưởng EPS dự phóng hai con số, định giá hấp dẫn với PEG &lt; 1.0 và dòng tiền khối ngoại mua ròng.
              </p>
            </div>

            <div className="pt-3 mt-3 border-t border-[#E1E7EF] flex justify-between items-center text-xs">
              <span className="text-[#68788C]">Kỳ vọng Upside:</span>
              <strong className="text-[#188253] font-bold font-mono-numbers">+{18 + idx * 3}%</strong>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

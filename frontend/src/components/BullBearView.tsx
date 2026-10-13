import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface BullBearViewProps {
  stock: StockData;
}

export const BullBearView: React.FC<BullBearViewProps> = ({ stock }) => {
  const [bullVotes, setBullVotes] = useState(84);
  const [bearVotes, setBearVotes] = useState(16);
  const [hasVoted, setHasVoted] = useState<'bull' | 'bear' | null>(null);

  const handleVote = (type: 'bull' | 'bear') => {
    if (hasVoted) return;
    if (type === 'bull') {
      setBullVotes(v => v + 1);
      setHasVoted('bull');
    } else {
      setBearVotes(v => v + 1);
      setHasVoted('bear');
    }
  };

  const totalVotes = bullVotes + bearVotes;
  const bullPct = Math.round((bullVotes / totalVotes) * 100);
  const bearPct = 100 - bullPct;

  return (
    <div className="space-y-4">
      {/* Banner */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#001735]">balance</span>
            <h2 className="text-base font-bold text-[#001735]">
              Hội Đồng Phản Biện: Bull vs Bear Case ({stock.symbol})
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Cân bằng giữa kỳ vọng tăng trưởng bứt phá và các rủi ro tiềm ẩn được tổng hợp từ 18 công ty chứng khoán & thuật toán AI StockLens.
          </p>
        </div>

        {/* Community Sentiment Bar */}
        <div className="w-full md:w-72 bg-[#F8F9FF] p-2.5 rounded-lg border border-[#E1E7EF]">
          <div className="flex justify-between text-xs font-bold mb-1">
            <span className="text-[#188253]">Phe Bò (Bull): {bullPct}%</span>
            <span className="text-[#C04B4B]">Phe Gấu (Bear): {bearPct}%</span>
          </div>
          <div className="w-full h-2 bg-[#FCEBEC] rounded-full overflow-hidden flex">
            <div className="bg-[#188253] h-full transition-all duration-300" style={{ width: `${bullPct}%` }}></div>
            <div className="bg-[#C04B4B] h-full transition-all duration-300" style={{ width: `${bearPct}%` }}></div>
          </div>
          <div className="flex justify-between items-center mt-2">
            <button
              disabled={!!hasVoted}
              onClick={() => handleVote('bull')}
              className={`text-[11px] font-semibold px-2 py-0.5 rounded cursor-pointer transition-all ${
                hasVoted === 'bull' ? 'bg-[#188253] text-white' : 'bg-[#E6F4EC] text-[#188253] hover:bg-[#188253] hover:text-white'
              }`}
            >
              + Bầu Bull Case
            </button>
            <button
              disabled={!!hasVoted}
              onClick={() => handleVote('bear')}
              className={`text-[11px] font-semibold px-2 py-0.5 rounded cursor-pointer transition-all ${
                hasVoted === 'bear' ? 'bg-[#C04B4B] text-white' : 'bg-[#FCEBEC] text-[#C04B4B] hover:bg-[#C04B4B] hover:text-white'
              }`}
            >
              + Bầu Bear Case
            </button>
          </div>
        </div>
      </div>

      {/* Grid Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bull Case */}
        <div className="bg-white rounded-xl border-2 border-[#188253]/30 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E1E7EF]">
            <h3 className="text-sm font-bold text-[#188253] flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px]">trending_up</span>
              LUẬN ĐIỂM TĂNG GIÁ (BULL CASE)
            </h3>
            <span className="text-xs font-bold text-[#188253] bg-[#E6F4EC] px-2.5 py-0.5 rounded-full">
              Kỳ vọng Upside: +24.8%
            </span>
          </div>

          <div className="space-y-3 text-xs leading-relaxed">
            {stock.bullCase.map((item, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-[#E6F4EC]/40 border border-[#188253]/20">
                <p className="font-semibold text-[#001735] mb-1">
                  Luận điểm {idx + 1}: {item}
                </p>
                <p className="text-[#44474E] text-[11px]">
                  Tác động lượng hóa: Đóng góp tăng trưởng EPS thêm +6.2% trong năm tài chính 2024-2025 theo mô hình chiết khấu FCFF.
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Bear Case */}
        <div className="bg-white rounded-xl border-2 border-[#C04B4B]/30 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E1E7EF]">
            <h3 className="text-sm font-bold text-[#C04B4B] flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px]">trending_down</span>
              LUẬN ĐIỂM RỦI RO (BEAR CASE)
            </h3>
            <span className="text-xs font-bold text-[#C04B4B] bg-[#FCEBEC] px-2.5 py-0.5 rounded-full">
              Kháng cự định giá
            </span>
          </div>

          <div className="space-y-3 text-xs leading-relaxed">
            {stock.bearCase.map((item, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-[#FCEBEC]/40 border border-[#C04B4B]/20">
                <p className="font-semibold text-[#001735] mb-1">
                  Rủi ro {idx + 1}: {item}
                </p>
                <p className="text-[#44474E] text-[11px]">
                  Biện pháp phòng ngừa: Đặt ngưỡng cắt lỗ kỹ thuật tại vùng hỗ trợ then chốt {stock.supportS1.toFixed(1)}k (SMA50).
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

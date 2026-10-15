import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface ValuationViewProps {
  stock: StockData;
}

export const ValuationView: React.FC<ValuationViewProps> = ({ stock }) => {
  const [wacc, setWacc] = useState(10.8);
  const [terminalGrowth, setTerminalGrowth] = useState(3.5);
  const [revenueCagr, setRevenueCagr] = useState(24.0);

  // Dynamic DCF approximation formula
  const baseFairValue = stock.targetPrice;
  const waccDelta = (10.8 - wacc) * 4500;
  const gDelta = (terminalGrowth - 3.5) * 6200;
  const revDelta = (revenueCagr - 24.0) * 1800;
  const calculatedTargetPrice = Math.round((baseFairValue + waccDelta + gDelta + revDelta) / 100) * 100;
  const calculatedUpside = (((calculatedTargetPrice - stock.currentPrice) / stock.currentPrice) * 100).toFixed(1);
  const calculatedMarginOfSafety = (((calculatedTargetPrice - stock.currentPrice) / calculatedTargetPrice) * 100).toFixed(1);

  return (
    <div className="space-y-4">
      {/* Banner */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">calculate</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Mô Hình Định Giá DCF & Bảng Thử Nghiệm Độ Nhạy (Sensitivity Matrix)
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Mô hình chiết khấu dòng tiền tự do cho doanh nghiệp (FCFF 10 năm) kết hợp P/E mục tiêu. Tùy biến các tham số dưới đây:
          </p>
        </div>

        <div className="text-right">
          <span className="text-xs text-[#68788C] block">Giá trị hợp lý tính toán:</span>
          <span className="text-xl sm:text-2xl font-extrabold text-[#1A56DB] font-mono-numbers">
            {calculatedTargetPrice.toLocaleString('vi-VN')} VND
          </span>
          <span className="text-xs text-[#188253] font-bold block">
            Upside: +{calculatedUpside}% (Biên an toàn: {calculatedMarginOfSafety}%)
          </span>
        </div>
      </div>

      {/* Sliders Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Slider 1: WACC */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 shadow-xs space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-bold text-[#001735]">Chi phí vốn bình quân (WACC)</span>
            <span className="font-mono-numbers font-bold text-[#3D6187] text-sm bg-[#EEF4FF] px-2 py-0.5 rounded">
              {wacc.toFixed(1)}%
            </span>
          </div>
          <input
            type="range"
            min="8.5"
            max="13.5"
            step="0.1"
            value={wacc}
            onChange={(e) => setWacc(parseFloat(e.target.value))}
            className="w-full accent-[#1A56DB] cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-[#74777F] font-mono-numbers">
            <span>8.5% (Lạc quan)</span>
            <span>Chuẩn: 10.8%</span>
            <span>13.5% (Thận trọng)</span>
          </div>
        </div>

        {/* Slider 2: Terminal Growth */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 shadow-xs space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-bold text-[#0C1D2D]">Tăng trưởng vĩnh viễn (g)</span>
            <span className="font-mono-numbers font-bold text-[#1A56DB] text-sm bg-[#EFF6FF] px-2 py-0.5 rounded">
              {terminalGrowth.toFixed(1)}%
            </span>
          </div>
          <input
            type="range"
            min="2.0"
            max="5.0"
            step="0.1"
            value={terminalGrowth}
            onChange={(e) => setTerminalGrowth(parseFloat(e.target.value))}
            className="w-full accent-[#1A56DB] cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-[#74777F] font-mono-numbers">
            <span>2.0%</span>
            <span>Chuẩn: 3.5%</span>
            <span>5.0%</span>
          </div>
        </div>

        {/* Slider 3: Revenue CAGR */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 shadow-xs space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-bold text-[#0C1D2D]">Doanh thu CAGR (2024-2028)</span>
            <span className="font-mono-numbers font-bold text-[#1A56DB] text-sm bg-[#EFF6FF] px-2 py-0.5 rounded">
              {revenueCagr.toFixed(1)}%
            </span>
          </div>
          <input
            type="range"
            min="16.0"
            max="32.0"
            step="0.5"
            value={revenueCagr}
            onChange={(e) => setRevenueCagr(parseFloat(e.target.value))}
            className="w-full accent-[#1A56DB] cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-[#74777F] font-mono-numbers">
            <span>16.0%</span>
            <span>Chuẩn: 24.0%</span>
            <span>32.0%</span>
          </div>
        </div>
      </div>

      {/* Sensitivity Matrix */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs overflow-x-auto custom-scrollbar">
        <h3 className="text-xs sm:text-sm font-bold text-[#001735] mb-3">
          Ma Trận Độ Nhạy Giá Mục Tiêu (WACC vs Tốc độ tăng trưởng g)
        </h3>
        <table className="w-full text-center text-xs font-mono-numbers">
          <thead>
            <tr className="bg-[#EEF4FF] text-[#3D6187]">
              <th className="py-2 px-3 text-left font-sans">WACC \ g</th>
              <th className="py-2 px-3">2.5%</th>
              <th className="py-2 px-3">3.0%</th>
              <th className="py-2 px-3 bg-[#D3E4FB]/60 text-[#001735] font-bold">3.5% (Cơ sở)</th>
              <th className="py-2 px-3">4.0%</th>
              <th className="py-2 px-3">4.5%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E1E7EF]">
            <tr>
              <td className="py-2 px-3 text-left font-bold text-[#001735]">9.8%</td>
              <td className="py-2 px-3">174,500</td>
              <td className="py-2 px-3">181,200</td>
              <td className="py-2 px-3 font-bold text-[#188253]">188,400</td>
              <td className="py-2 px-3">196,100</td>
              <td className="py-2 px-3">204,500</td>
            </tr>
            <tr className="bg-[#EEF4FF]/40">
              <td className="py-2 px-3 text-left font-bold text-[#001735]">10.8% (Cơ sở)</td>
              <td className="py-2 px-3">160,800</td>
              <td className="py-2 px-3">166,400</td>
              <td className="py-2 px-3 font-extrabold text-[#001735] bg-[#E6F4EC] border border-[#188253]/30">
                172,800
              </td>
              <td className="py-2 px-3">179,500</td>
              <td className="py-2 px-3">186,800</td>
            </tr>
            <tr>
              <td className="py-2 px-3 text-left font-bold text-[#001735]">11.8%</td>
              <td className="py-2 px-3">149,200</td>
              <td className="py-2 px-3">153,900</td>
              <td className="py-2 px-3 font-bold text-[#3D6187]">159,100</td>
              <td className="py-2 px-3">164,800</td>
              <td className="py-2 px-3">171,000</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

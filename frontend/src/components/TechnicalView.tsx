import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface TechnicalViewProps {
  stock: StockData;
}

export const TechnicalView: React.FC<TechnicalViewProps> = ({ stock }) => {
  const [indicatorTab, setIndicatorTab] = useState<'all' | 'ma' | 'oscillators' | 'pivot'>('all');

  const maData = [
    { name: 'SMA 10', value: 136.2, signal: 'MUA', color: 'text-[#188253]' },
    { name: 'SMA 20', value: stock.sma20, signal: 'MUA', color: 'text-[#188253]' },
    { name: 'SMA 50', value: stock.sma50, signal: 'MUA', color: 'text-[#188253]' },
    { name: 'SMA 100', value: 121.5, signal: 'MUA MẠNH', color: 'text-[#188253]' },
    { name: 'SMA 200', value: 108.4, signal: 'MUA MẠNH', color: 'text-[#188253]' },
    { name: 'EMA 20', value: 135.8, signal: 'MUA', color: 'text-[#188253]' },
  ];

  const pivotLevels = [
    { level: 'Kháng cự R3', price: 146.5, diff: '+5.8%' },
    { level: 'Kháng cự R2', price: 144.0, diff: '+4.0%' },
    { level: 'Kháng cự R1', price: stock.resistanceR1, diff: '+2.5%' },
    { level: 'Điểm xoay Pivot (P)', price: 136.8, diff: '-1.2%' },
    { level: 'Hỗ trợ S1', price: stock.supportS1, diff: '-4.0%' },
    { level: 'Hỗ trợ S2', price: 130.5, diff: '-5.8%' },
    { level: 'Hỗ trợ S3', price: 126.0, diff: '-9.0%' },
  ];

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">show_chart</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Phân Tích Kỹ Thuật & Dòng Tiền Đa Khung Thời Gian
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Mô hình nhận diện mẫu hình nến Bullish Continuation, chỉ báo động lượng và các vùng cản trọng yếu.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[#E6F4EC] text-[#188253] border border-[#188253]/20">
            Tín hiệu tổng hợp: MUA MẠNH
          </span>
          <span className="text-xs font-mono-numbers px-2.5 py-1 rounded bg-[#EFF6FF] text-[#1A56DB] font-bold border border-[#BFDBFE]">
            14 MUA / 2 TRUNG LẬP / 0 BÁN
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Moving Averages Table */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E1E7EF]">
            <h3 className="text-xs sm:text-sm font-bold text-[#1A56DB] flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-[#3D6187]">timeline</span>
              Đường Trung Bình Động (Moving Averages)
            </h3>
            <span className="text-[11px] text-[#188253] font-bold">Xu hướng: Tăng vững chắc</span>
          </div>

          <div className="divide-y divide-[#E1E7EF] text-xs">
            {maData.map((item, i) => (
              <div key={i} className="py-2.5 flex items-center justify-between hover:bg-[#EEF4FF]/30 px-1 rounded transition-colors">
                <span className="font-semibold text-[#0C1D2D]">{item.name}</span>
                <span className="font-mono-numbers text-[#44474E]">{item.value.toFixed(1)}k</span>
                <span className={`font-bold ${item.color} px-2 py-0.5 rounded bg-[#E6F4EC]/60`}>
                  {item.signal}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Pivot Points & Fibonacci */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E1E7EF]">
            <h3 className="text-xs sm:text-sm font-bold text-[#001735] flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-[#3D6187]">tune</span>
              Vùng Điểm Xoay Pivot & Hỗ Trợ / Kháng Cự
            </h3>
            <span className="text-[11px] text-[#3D6187] font-medium">Khung Daily Classic</span>
          </div>

          <div className="divide-y divide-[#E1E7EF] text-xs">
            {pivotLevels.map((p, i) => (
              <div key={i} className="py-2 flex items-center justify-between hover:bg-[#EEF4FF]/30 px-1 rounded transition-colors">
                <span className={`font-medium ${p.level.includes('Kháng cự') ? 'text-[#C04B4B]' : p.level.includes('Hỗ trợ') ? 'text-[#188253]' : 'text-[#001735] font-bold'}`}>
                  {p.level}
                </span>
                <span className="font-mono-numbers font-bold text-[#0C1D2D]">
                  {p.price.toFixed(1)}k
                </span>
                <span className={`font-mono-numbers text-[11px] font-semibold ${p.diff.startsWith('+') ? 'text-[#C04B4B]' : 'text-[#188253]'}`}>
                  {p.diff}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

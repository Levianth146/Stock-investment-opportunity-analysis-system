import React from 'react';
import { StockData } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface CompanyProfileModalProps {
  stock: StockData;
  isOpen: boolean;
  onClose: () => void;
}

export const CompanyProfileModal: React.FC<CompanyProfileModalProps> = ({
  stock,
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const overview = stock.companyOverview;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 lg:p-6 select-none animate-in fade-in duration-200">
      {/* Backdrop */}
      <div 
        onClick={onClose}
        className="absolute inset-0 bg-[#001735]/40 backdrop-blur-xs cursor-pointer"
      ></div>

      {/* Modal Dialog */}
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-white rounded-2xl shadow-2xl border border-[#E1E7EF] flex flex-col overflow-hidden z-20">
        
        {/* Modal Header */}
        <div className="p-5 bg-gradient-to-r from-[#1A56DB] to-[#2563EB] text-white flex items-center justify-between flex-none">
          <div className="flex items-center gap-3.5">
            <CompanyLogo symbol={stock.symbol} size="lg" className="bg-white/95" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">{stock.name}</h2>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-white/20 text-white border border-white/30">
                  {stock.exchange}: {stock.symbol}
                </span>
              </div>
              <p className="text-xs text-white/90 mt-0.5">
                {stock.industry} • Thành lập năm {overview.foundingYear} • {overview.marketPosition}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white/80 hover:text-white hover:bg-white/20 transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6">
          
          {/* Section 1: Giới thiệu tổng quan */}
          <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E40AF] mb-2 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px]">info</span>
              Tổng Quan & Vị Thế Thị Trường
            </h3>
            <p className="text-xs sm:text-sm text-[#1E3A8A] leading-relaxed">
              {overview.shortDescription}
            </p>
          </div>

          {/* Section 2: Thông tin cơ bản & Ban lãnh đạo (Grid 2 cols) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Box 1: Thông tin pháp lý & quy mô */}
            <div className="bg-white border border-[#E1E7EF] rounded-xl p-4 space-y-2.5 shadow-xs">
              <h4 className="text-xs font-bold text-[#1A56DB] uppercase tracking-wide flex items-center gap-1.5 border-b border-[#E1E7EF] pb-2">
                <span className="material-symbols-outlined text-[16px]">domain</span>
                Thông Tin Doanh Nghiệp
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-[#68788C]">Năm thành lập:</span>
                  <span className="font-bold text-[#0C1D2D] font-mono-numbers">{overview.foundingYear}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#68788C]">Quy mô nhân sự:</span>
                  <span className="font-bold text-[#0C1D2D]">{overview.employees}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#68788C]">Vốn hóa thị trường:</span>
                  <span className="font-bold text-[#1A56DB] font-mono-numbers">{stock.marketCap}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#68788C]">Trụ sở chính:</span>
                  <span className="font-medium text-[#0C1D2D] text-right truncate max-w-[180px]" title={overview.headquarters}>
                    {overview.headquarters}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-1 border-t border-[#E1E7EF]/70">
                  <span className="text-[#68788C]">Website chính thức:</span>
                  <a 
                    href={overview.website} 
                    target="_blank" 
                    rel="noreferrer" 
                    className="text-[#1A56DB] hover:underline font-semibold flex items-center gap-1"
                  >
                    <span>{overview.website.replace('https://', '')}</span>
                    <span className="material-symbols-outlined text-[13px]">open_in_new</span>
                  </a>
                </div>
              </div>
            </div>

            {/* Box 2: Ban lãnh đạo */}
            <div className="bg-white border border-[#E1E7EF] rounded-xl p-4 space-y-2.5 shadow-xs">
              <h4 className="text-xs font-bold text-[#1A56DB] uppercase tracking-wide flex items-center gap-1.5 border-b border-[#E1E7EF] pb-2">
                <span className="material-symbols-outlined text-[16px]">badge</span>
                Ban Lãnh Đạo Chủ Chốt
              </h4>
              <div className="space-y-3 text-xs pt-1">
                <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                  <span className="text-[10px] text-[#68788C] block uppercase font-bold">Chủ tịch Hội đồng Quản trị</span>
                  <span className="text-sm font-bold text-[#0C1D2D]">{overview.leadership.chairman}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                  <span className="text-[10px] text-[#68788C] block uppercase font-bold">Tổng Giám Đốc (CEO)</span>
                  <span className="text-sm font-bold text-[#0C1D2D]">{overview.leadership.ceo}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Cơ cấu khối ngành kinh doanh */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0C1D2D] mb-3 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-[#1A56DB]">account_tree</span>
              Cơ Cấu Khối Kinh Doanh Cốt Lõi
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {overview.coreSegments.map((seg, i) => (
                <div key={i} className="bg-white border border-[#E1E7EF] rounded-xl p-3.5 shadow-xs space-y-2 hover:border-[#1A56DB] transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0C1D2D]">{seg.name}</span>
                    <span className="text-[11px] font-bold text-[#1A56DB] bg-[#EFF6FF] px-2 py-0.5 rounded font-mono-numbers">
                      {seg.revenueShare}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#44474E] leading-relaxed">
                    {seg.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Section 4: Động lực tăng trưởng chiến lược */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0C1D2D] mb-3 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-[#188253]">trending_up</span>
              Động Lực Tăng Trưởng Chiến Lược 2024 - 2026
            </h3>
            <div className="space-y-2">
              {overview.growthDrivers.map((driver, i) => (
                <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF] text-xs">
                  <span className="w-5 h-5 rounded-full bg-[#E6F4EC] text-[#188253] flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5">
                    ✓
                  </span>
                  <span className="text-[#0C1D2D] font-medium leading-relaxed">
                    {driver}
                  </span>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-[#F8F9FF] border-t border-[#E1E7EF] flex justify-end gap-2 flex-none">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#1A56DB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
          >
            Đóng hồ sơ
          </button>
        </div>
      </div>
    </div>
  );
};

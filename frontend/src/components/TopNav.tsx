import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface TopNavProps {
  currentStock: StockData;
  activeNavTab: string;
  setActiveNavTab: (tab: string) => void;
  onOpenPdfModal: () => void;
  onOpenSearch: () => void;
  isBookmarked: boolean;
  onToggleBookmark: () => void;
  onOpenCopilot: () => void;
  onOpenHoseBoard: () => void;
}

export const TopNav: React.FC<TopNavProps> = ({
  currentStock,
  activeNavTab,
  setActiveNavTab,
  onOpenPdfModal,
  onOpenSearch,
  isBookmarked,
  onToggleBookmark,
  onOpenHoseBoard,
}) => {
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <header className="bg-white border-b border-[#E1E7EF] sticky top-0 z-40 shadow-xs flex-none">
      <div className="flex items-center justify-between px-4 sm:px-6 py-2.5 w-full max-w-7xl mx-auto gap-4">
        {/* Brand & Search cluster */}
        <div className="flex items-center gap-4 sm:gap-6 min-w-0">
          <button 
            onClick={() => setActiveNavTab('Tổng quan')} 
            className="flex items-center gap-2.5 flex-shrink-0 text-left cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1A56DB] to-[#2563EB] text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-sm group-hover:from-[#1D4ED8] group-hover:to-[#1A56DB] transition-all">
              SL
            </div>
            <div>
              <div className="text-base font-bold tracking-tight text-[#0C1D2D] leading-tight">
                StockLens VN
              </div>
              <div className="text-[9px] font-semibold tracking-wider text-[#1A56DB] uppercase leading-none hidden sm:block">
                HỆ THỐNG ĐỊNH LƯỢNG VỐN
              </div>
            </div>
          </button>

          {/* Left Search Bar with Active Symbol */}
          <div className="relative w-56 sm:w-64 md:w-72">
            <button
              onClick={onOpenSearch}
              className="w-full flex items-center justify-between pl-9 pr-3 py-1.5 bg-[#EFF6FF] hover:bg-[#DBEAFE] border border-[#BFDBFE] rounded-lg text-xs font-semibold text-[#0C1D2D] transition-all cursor-pointer text-left"
            >
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#1A56DB]">
                <span className="material-symbols-outlined text-[18px]">search</span>
              </div>
              <span className="truncate">{currentStock.symbol} - {currentStock.name}</span>
              <span className="text-[10px] font-medium text-[#1A56DB] bg-white px-1.5 py-0.5 rounded border border-[#BFDBFE] ml-1 flex-shrink-0">
                ⌘K
              </span>
            </button>
          </div>
        </div>

        {/* Navigation Links Cluster */}
        <nav className="hidden lg:flex items-center gap-6 pt-1">
          <button
            onClick={() => setActiveNavTab('Tổng quan')}
            className={`pb-2 text-xs font-semibold transition-colors border-b-2 ${
              activeNavTab === 'Tổng quan'
                ? 'text-[#1A56DB] border-[#1A56DB]'
                : 'text-[#44474E] hover:text-[#1A56DB] border-transparent'
            }`}
          >
            Tổng quan
          </button>
          <button
            onClick={onOpenHoseBoard}
            className={`pb-2 text-xs font-semibold transition-colors border-b-2 flex items-center gap-1.5 ${
              activeNavTab === 'Bảng điện HOSE'
                ? 'text-[#1A56DB] border-[#1A56DB]'
                : 'text-[#44474E] hover:text-[#1A56DB] border-transparent'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#188253] animate-pulse"></span>
            Bảng điện HOSE
          </button>
          <button
            onClick={() => setActiveNavTab('Danh mục theo dõi')}
            className={`pb-2 text-xs font-semibold transition-colors border-b-2 flex items-center gap-1.5 ${
              activeNavTab === 'Danh mục theo dõi'
                ? 'text-[#1A56DB] border-[#1A56DB]'
                : 'text-[#44474E] hover:text-[#1A56DB] border-transparent'
            }`}
          >
            <span>Danh mục theo dõi</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[#EFF6FF] text-[#1A56DB] font-bold">
              12
            </span>
          </button>
          <button
            onClick={() => setActiveNavTab('Báo cáo AI')}
            className={`pb-2 text-xs font-semibold transition-colors border-b-2 flex items-center gap-1.5 ${
              activeNavTab === 'Báo cáo AI'
                ? 'text-[#1A56DB] border-[#1A56DB]'
                : 'text-[#44474E] hover:text-[#1A56DB] border-transparent'
            }`}
          >
            <span>Báo cáo AI</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[#F0E7FC] text-[#6B46C1] font-bold">
              4
            </span>
          </button>
          <button
            onClick={() => setActiveNavTab('Khuyến nghị đầu tư')}
            className={`pb-2 text-xs font-semibold transition-colors border-b-2 ${
              activeNavTab === 'Khuyến nghị đầu tư'
                ? 'text-[#1A56DB] border-[#1A56DB]'
                : 'text-[#44474E] hover:text-[#1A56DB] border-transparent'
            }`}
          >
            Khuyến nghị đầu tư
          </button>
        </nav>

        {/* Trailing Actions & Profile */}
        <div className="flex items-center gap-2 sm:gap-2.5 flex-shrink-0">
          {/* Secondary Action: Theo dõi */}
          <button
            onClick={onToggleBookmark}
            className={`hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
              isBookmarked
                ? 'bg-[#FFF4D8] border-[#B7791F]/40 text-[#B7791F]'
                : 'border-[#BFDBFE] text-[#1A56DB] hover:bg-[#EFF6FF]'
            }`}
            title="Thêm hoặc xóa cổ phiếu khỏi danh mục theo dõi"
          >
            <span className={`material-symbols-outlined text-[16px] ${isBookmarked ? 'fill-current' : ''}`}>
              {isBookmarked ? 'bookmark_added' : 'bookmark'}
            </span>
            <span>{isBookmarked ? 'Đã theo dõi' : 'Theo dõi'}</span>
          </button>

          {/* Primary Action Active Trigger: Xuất Báo Cáo PDF */}
          <button
            onClick={onOpenPdfModal}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#1A56DB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-sm transition-all active:scale-95 ring-2 ring-[#1A56DB]/20 cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
            <span className="whitespace-nowrap">Xuất Báo Cáo PDF</span>
          </button>

          {/* Trailing Icon Actions */}
          <div className="flex items-center gap-1 border-l border-[#E1E7EF] pl-1.5 sm:pl-2 relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-1.5 text-[#3D6187] hover:text-[#1A56DB] hover:bg-[#EFF6FF] rounded-lg transition-colors relative cursor-pointer"
              title="Thông báo tín hiệu"
            >
              <span className="material-symbols-outlined text-[18px]">notifications</span>
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[#C04B4B]"></span>
            </button>
            <button
              onClick={onOpenSearch}
              className="p-1.5 text-[#3D6187] hover:text-[#1A56DB] hover:bg-[#EFF6FF] rounded-lg transition-colors cursor-pointer"
              title="Chuyển đổi cổ phiếu"
            >
              <span className="material-symbols-outlined text-[18px]">swap_horiz</span>
            </button>

            {/* Notifications Dropdown */}
            {showNotifications && (
              <div className="absolute right-0 top-10 w-80 bg-white rounded-xl shadow-xl border border-[#E1E7EF] p-3 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="flex items-center justify-between pb-2 border-b border-[#E1E7EF]">
                  <span className="text-xs font-bold text-[#1A56DB]">Thông báo định lượng</span>
                  <span className="text-[10px] text-[#3D6187] cursor-pointer hover:underline">Đã đọc tất cả</span>
                </div>
                <div className="space-y-2 mt-2 text-xs">
                  <div className="p-2 rounded-lg bg-[#E6F4EC] border border-[#188253]/20">
                    <p className="font-semibold text-[#188253] text-[11px] flex items-center gap-1">
                      <span className="material-symbols-outlined text-[14px]">trending_up</span>
                      Tín hiệu Mua mạnh: {currentStock.symbol}
                    </p>
                    <p className="text-[10px] text-[#0C1D2D] mt-0.5">
                      Điểm mô hình tăng lên {currentStock.aiScore}/100 sau cập nhật KQKD Q3.
                    </p>
                  </div>
                  <div className="p-2 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE]">
                    <p className="font-semibold text-[#1A56DB] text-[11px]">Báo cáo mới sẵn sàng</p>
                    <p className="text-[10px] text-[#44474E] mt-0.5">
                      Bản thẩm định chuyên sâu {currentStock.symbol} Q3/2024 đã được cập nhật mô hình DCF.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

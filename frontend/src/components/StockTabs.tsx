import React from 'react';

export type SubTabType = 
  | 'overview'
  | 'technical'
  | 'financials'
  | 'valuation'
  | 'news'
  | 'risks'
  | 'bullbear';

interface StockTabsProps {
  activeTab: SubTabType;
  setActiveTab: (tab: SubTabType) => void;
}

export const StockTabs: React.FC<StockTabsProps> = ({ activeTab, setActiveTab }) => {
  const tabs = [
    { id: 'overview' as SubTabType, label: 'Tổng quan', icon: 'grid_view' },
    { id: 'technical' as SubTabType, label: 'Phân tích kỹ thuật (T)', icon: 'show_chart' },
    { id: 'financials' as SubTabType, label: 'BCTC & Cơ bản (F)', icon: 'account_balance' },
    { id: 'valuation' as SubTabType, label: 'Định giá & Target (V)', icon: 'calculate' },
    { id: 'news' as SubTabType, label: 'Tin tức & AI Sentiment (S)', icon: 'newspaper' },
    { id: 'risks' as SubTabType, label: 'Rủi ro & Kiểm toán (R)', icon: 'shield_lock' },
    { id: 'bullbear' as SubTabType, label: 'Bull vs Bear', icon: 'balance' },
  ];

  return (
    <div className="bg-white rounded-xl border border-[#E1E7EF] p-1.5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-2 overflow-x-auto custom-scrollbar">
      {/* Scrollable tabs bar */}
      <div className="flex items-center gap-1 min-w-max">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#1A56DB] text-white shadow-xs'
                  : 'text-[#3D6187] hover:text-[#1A56DB] hover:bg-[#EFF6FF]'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Trailing live gateway badge */}
      <div className="hidden xl:flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#188253] bg-[#E6F4EC] rounded-lg border border-[#188253]/20 flex-shrink-0">
        <span className="material-symbols-outlined text-[16px] text-[#188253]">verified</span>
        <span className="font-medium text-[11px]">
          Dữ liệu khớp lệnh trực tiếp: <strong className="font-bold">HOSE Gateway</strong>
        </span>
      </div>
    </div>
  );
};

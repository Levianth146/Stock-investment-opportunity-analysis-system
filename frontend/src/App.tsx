import React, { useState, useEffect } from 'react';
import { STOCKS_DATA, StockData } from './data/stocks';
import { TopNav } from './components/TopNav';
import { StockHeader } from './components/StockHeader';
import { StockTabs, SubTabType } from './components/StockTabs';
import { OverviewView } from './components/OverviewView';
import { TechnicalView } from './components/TechnicalView';
import { FinancialsView } from './components/FinancialsView';
import { ValuationView } from './components/ValuationView';
import { NewsSentimentView } from './components/NewsSentimentView';
import { RisksAuditView } from './components/RisksAuditView';
import { BullBearView } from './components/BullBearView';
import { WatchlistView } from './components/WatchlistView';
import { ReportsLibraryView } from './components/ReportsLibraryView';
import { RecommendationsView } from './components/RecommendationsView';
import { PdfExportModal } from './components/PdfExportModal';
import { HoseBoardModal } from './components/HoseBoardModal';
import { AiCopilotDrawer } from './components/AiCopilotDrawer';
import { TickerSearchModal } from './components/TickerSearchModal';
import { CompanyProfileModal } from './components/CompanyProfileModal';

export default function App() {
  const API_URL = "http://127.0.0.1:8000/api/analyze";

  const [currentSymbol, setCurrentSymbol] = useState<string>('FPT');
  const [activeNavTab, setActiveNavTab] = useState<string>('Tổng quan');
  const [activeSubTab, setActiveSubTab] = useState<SubTabType>('overview');

  // State lưu trữ dữ liệu thật từ Backend FastAPI
  const [liveStockData, setLiveStockData] = useState<StockData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Modals & Drawers state
  const [isPdfModalOpen, setIsPdfModalOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isHoseBoardOpen, setIsHoseBoardOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [isCompanyProfileOpen, setIsCompanyProfileOpen] = useState(false);

  // Watchlist favorite status
  const [watchlistedSymbols, setWatchlistedSymbols] = useState<string[]>(['FPT', 'HPG', 'VNM']);

  // Ưu tiên dữ liệu từ backend, nếu null thì fallback về STOCKS_DATA
  const currentStock: StockData = liveStockData || STOCKS_DATA[currentSymbol] || STOCKS_DATA['FPT'];
  const isBookmarked = watchlistedSymbols.includes(currentSymbol);

  const handleToggleBookmark = () => {
    if (isBookmarked) {
      setWatchlistedSymbols(prev => prev.filter(s => s !== currentSymbol));
    } else {
      setWatchlistedSymbols(prev => [...prev, currentSymbol]);
    }
  };

  // Hàm gọi API tới Backend FastAPI Python
  const fetchStockAnalysis = async (symbol: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ticker: symbol,
          profile: "long_term",
          as_of: "2026-10-09",
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("Dữ liệu nhận từ Python Backend:", result);

      // Cập nhật dữ liệu vào giao diện (map theo schema của StockData)
      // Giữ lại cấu trúc hiện tại và ghi đè các thông tin phân tích mới
      const baseStock = STOCKS_DATA[symbol] || STOCKS_DATA['FPT'];
      const recommendationMap: Record<string, StockData['aiRecommendation']> = {
        'Hấp dẫn': 'MUA',
        'MUA MẠNH': 'MUA MẠNH',
        'MUA': 'MUA',
        'GIỮ': 'GIỮ',
        'BÁN': 'BÁN',
      };

      setLiveStockData({
        ...baseStock,
        symbol: result.ticker || symbol,
        targetPrice: result.target_price || baseStock.targetPrice,
        aiRecommendation: recommendationMap[result.recommendation] || baseStock.aiRecommendation,
        // Nếu backend trả về scores hoặc debate, có thể ghi đè tiếp ở đây
      });
    } catch (err) {
      console.error("Không kết nối được tới backend 8000, dùng dữ liệu offline:", err);
      // Fallback về mock data nếu backend tắt
      setLiveStockData(STOCKS_DATA[symbol] || STOCKS_DATA['FPT']);
    } finally {
      setIsLoading(false);
    }
  };

  // Tự động gọi API khi currentSymbol thay đổi
  useEffect(() => {
    fetchStockAnalysis(currentSymbol);
  }, [currentSymbol]);

  const handleSelectStock = (symbol: string) => {
    setCurrentSymbol(symbol);
    setActiveNavTab('Tổng quan');
    setActiveSubTab('overview');
  };

  return (
    <div className="min-h-screen bg-[#F8F9FF] text-[#0C1D2D] flex flex-col font-sans selection:bg-[#AED2FD] selection:text-[#001D35]">
      {/* ================= TOP NAVIGATION ================= */}
      <TopNav
        currentStock={currentStock}
        activeNavTab={activeNavTab}
        setActiveNavTab={setActiveNavTab}
        onOpenPdfModal={() => setIsPdfModalOpen(true)}
        onOpenSearch={() => setIsSearchOpen(true)}
        isBookmarked={isBookmarked}
        onToggleBookmark={handleToggleBookmark}
        onOpenCopilot={() => setIsCopilotOpen(true)}
        onOpenHoseBoard={() => setIsHoseBoardOpen(true)}
      />

      {/* ================= MAIN CONTAINER ================= */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-4">
        {/* Render depending on Top Nav selection */}
        {activeNavTab === 'Danh mục theo dõi' ? (
          <WatchlistView onSelectStock={handleSelectStock} />
        ) : activeNavTab === 'Báo cáo AI' ? (
          <ReportsLibraryView 
            onOpenPdfModal={() => setIsPdfModalOpen(true)} 
            onSelectStock={handleSelectStock} 
          />
        ) : activeNavTab === 'Khuyến nghị đầu tư' ? (
          <RecommendationsView onSelectStock={handleSelectStock} />
        ) : (
          /* Active Stock Analysis Workspace */
          <div className="space-y-4">
            {/* Stock Identity Header */}
            <StockHeader
              stock={currentStock}
              isWatchlisted={isBookmarked}
              onToggleWatchlist={handleToggleBookmark}
              onOpenCopilot={() => setIsCopilotOpen(true)}
              onOpenCompanyProfile={() => setIsCompanyProfileOpen(true)}
            />

            {/* Sub-tab Navigation Ribbon */}
            <StockTabs
              activeTab={activeSubTab}
              setActiveTab={setActiveSubTab}
            />

            {/* Sub-tab Content Area */}
            {activeSubTab === 'overview' && (
              <OverviewView
                stock={currentStock}
                onNavigateTab={(tab) => setActiveSubTab(tab)}
                onOpenPdfModal={() => setIsPdfModalOpen(true)}
                onOpenCompanyProfile={() => setIsCompanyProfileOpen(true)}
              />
            )}

            {activeSubTab === 'technical' && (
              <TechnicalView stock={currentStock} />
            )}

            {activeSubTab === 'financials' && (
              <FinancialsView stock={currentStock} />
            )}

            {activeSubTab === 'valuation' && (
              <ValuationView stock={currentStock} />
            )}

            {activeSubTab === 'news' && (
              <NewsSentimentView stock={currentStock} />
            )}

            {activeSubTab === 'risks' && (
              <RisksAuditView stock={currentStock} />
            )}

            {activeSubTab === 'bullbear' && (
              <BullBearView stock={currentStock} />
            )}
          </div>
        )}
      </main>

      {/* ================= FOOTER ================= */}
      <footer className="bg-white border-t border-[#E1E7EF] py-4 px-4 sm:px-6 mt-8 flex-none">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between text-xs text-[#68788C] gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold text-[#1A56DB]">StockLens VN 2025</span>
            <span>• Nền tảng Định lượng & Tình báo Cổ phiếu Việt Nam</span>
            <span className="px-2 py-0.5 rounded bg-[#EFF6FF] text-[#1A56DB] font-mono-numbers font-semibold border border-[#BFDBFE]">
              Phiên bản Pro 3.4.1
            </span>
          </div>

          <p className="text-[11px] text-[#74777F] text-center md:text-right max-w-xl leading-relaxed">
            Miễn trừ trách nhiệm: Báo cáo nhằm mục đích tham khảo và phân tích định lượng dựa trên số liệu lịch sử. Nhà đầu tư tự chịu trách nhiệm với quyết định giao dịch của mình.
          </p>
        </div>
      </footer>

      {/* ================= MODALS & DRAWERS ================= */}
      {/* 1. PDF Export Modal with Live Preview */}
      <PdfExportModal
        stock={currentStock}
        isOpen={isPdfModalOpen}
        onClose={() => setIsPdfModalOpen(false)}
      />

      {/* 2. HOSE Electronic Board Stream Modal */}
      <HoseBoardModal
        isOpen={isHoseBoardOpen}
        onClose={() => setIsHoseBoardOpen(false)}
        onSelectStock={handleSelectStock}
        currentSymbol={currentSymbol}
      />

      {/* 3. AI Copilot Drawer */}
      <AiCopilotDrawer
        stock={currentStock}
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />

      {/* 4. Command Palette Ticker Search (⌘K) */}
      <TickerSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSelectStock={handleSelectStock}
      />

      {/* 5. Company Profile & Overview Modal */}
      <CompanyProfileModal
        stock={currentStock}
        isOpen={isCompanyProfileOpen}
        onClose={() => setIsCompanyProfileOpen(false)}
      />
    </div>
  );
}

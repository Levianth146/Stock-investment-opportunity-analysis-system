import React, { useEffect, useState } from 'react';
import { StockData } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface PdfExportModalProps {
  stock: StockData;
  isOpen: boolean;
  onClose: () => void;
}

export const PdfExportModal: React.FC<PdfExportModalProps> = ({
  stock,
  isOpen,
  onClose,
}) => {
  const [horizon, setHorizon] = useState<'short' | 'medium' | 'long'>('medium');
  const [language, setLanguage] = useState<'vi' | 'en'>('vi');
  const [docScope, setDocScope] = useState('Chuyên sâu (12 trang)');
  const [generationState, setGenerationState] = useState<'ready' | 'generating' | 'error'>('ready');
  const [activePage, setActivePage] = useState(1);
  const [zoomLevel, setZoomLevel] = useState(100);
  const [watermarkEnabled, setWatermarkEnabled] = useState(true);
  const [copiedLink, setCopiedLink] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [isPrinting, setIsPrinting] = useState(false);

  // Sections toggle state
  const [sections, setSections] = useState([
    { id: 'thesis', title: 'Tóm tắt Luận điểm & Khuyến nghị AI', sub: 'Investment Thesis, Điểm xếp hạng AI 8.8 & Upside', pages: 'Trang 1-2', checked: true },
    { id: 'financials', title: `Phân tích Cơ bản & Báo cáo Tài chính Q3/2024`, sub: 'Doanh thu, Biên lợi nhuận, Cơ cấu nợ & Lưu chuyển tiền tệ', pages: 'Trang 3-5', checked: true },
    { id: 'dcf', title: 'Mô hình Định giá DCF, P/E & So sánh Ngành', sub: 'WACC 10.8%, FCFF đa kịch bản & P/E mục tiêu 22.0x', pages: 'Trang 6-8', checked: true },
    { id: 'technical', title: 'Phân tích Kỹ thuật & Xu hướng Dòng tiền', sub: 'Hành vi dòng tiền Khối ngoại, Tự doanh & Khung RSI/MACD', pages: 'Trang 9-10', checked: true },
    { id: 'risks', title: 'Đánh giá Rủi ro, Ban lãnh đạo & ESG', sub: 'Ma trận rủi ro tỷ giá JPY/USD & Quản trị doanh nghiệp', pages: 'Trang 11', checked: true },
    { id: 'insider', title: 'Phụ lục Giao dịch Nội bộ & Cổ đông lớn', sub: 'Lịch sử đăng ký bán cổ phiếu & Tỷ lệ free-float', pages: '+ 2 trang', checked: false },
  ]);

  useEffect(() => {
    if (!isPrinting) return;

    const handleAfterPrint = () => setIsPrinting(false);
    window.addEventListener('afterprint', handleAfterPrint);
    const timeoutId = window.setTimeout(() => window.print(), 100);

    return () => {
      window.clearTimeout(timeoutId);
      window.removeEventListener('afterprint', handleAfterPrint);
    };
  }, [isPrinting]);

  if (!isOpen) return null;

  const toggleSection = (id: string) => {
    setSections(prev => prev.map(s => s.id === id ? { ...s, checked: !s.checked } : s));
  };

  const handleDownload = () => {
    setDownloading(true);
    setTimeout(() => {
      setDownloading(false);
      setIsPrinting(true);
    }, 800);
  };

  const handlePrint = () => setIsPrinting(true);

  const handleCopyLink = () => {
    navigator.clipboard?.writeText(window.location.href + `#report-${stock.symbol.toLowerCase()}`);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleSendEmail = () => {
    setEmailSent(true);
    setTimeout(() => setEmailSent(false), 2500);
  };

  return (
    <div className="pdf-export-modal fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 lg:p-6 select-none overflow-hidden animate-in fade-in duration-200">
      {/* Active Backdrop Scrim (Depth Level 3: Dimming backdrop 35% navy) */}
      <div 
        onClick={onClose}
        className="pdf-export-backdrop absolute inset-0 bg-[#001735]/40 backdrop-blur-[3px] transition-opacity cursor-pointer"
      ></div>

      {/* Dual-Panel Equity Research Export Modal */}
      <div className="pdf-export-shell relative w-full max-w-7xl h-[92vh] max-h-[890px] bg-white rounded-xl shadow-2xl border border-[#C4C6CF]/40 flex flex-col overflow-hidden z-20">
        
        {/* ================= MODAL HEADER BAR ================= */}
        <div className="pdf-export-header px-6 py-3.5 bg-white border-b border-[#E1E7EF] flex items-center justify-between flex-none">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] flex items-center justify-center text-[#1A56DB]">
              <span className="material-symbols-outlined text-[20px]">assignment</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold text-[#0C1D2D]">
                  Cấu hình & Xuất Báo Cáo Phân Tích Cổ Phiếu {stock.symbol}
                </h1>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#EFF6FF] text-[#1A56DB] border border-[#BFDBFE]">
                  Bản Thẩm Định Pro v4.2
                </span>
              </div>
              <p className="text-xs text-[#68788C]">
                Hệ thống tổng hợp báo cáo tài chính, mô hình định giá DCF, và khuyến nghị từ StockLens AI Engine
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => alert('Phương pháp luận StockLens v4.2 dựa trên: 1. Chiết khấu dòng tiền tự do FCFF (WACC 10.8%); 2. P/E trung vị ngành 5 năm; 3. Mô hình chấm điểm 5 nhân tố F-T-V-S-R.')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[#1A56DB] text-xs font-semibold hover:bg-[#EFF6FF] rounded-lg transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">help_outline</span>
              <span>Hướng dẫn phương pháp</span>
            </button>
            <div className="h-4 w-px bg-[#E1E7EF]"></div>
            <button 
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-[#68788C] hover:text-[#1A56DB] hover:bg-[#EFF6FF] transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        </div>

        {/* ================= SPLIT SCREEN BODY ================= */}
        <div className="pdf-export-body flex-1 grid grid-cols-12 overflow-hidden">
          
          {/* ================= LEFT PANEL: CONFIGURATION & EXPORT CONTROLS (5 Cols) ================= */}
          <section className="pdf-export-config col-span-12 lg:col-span-5 border-r border-[#E1E7EF] flex flex-col bg-white overflow-hidden">
            <div className="flex-1 overflow-y-auto custom-scrollbar p-5 sm:p-6 space-y-5">
              
              {/* Parameter 1: Khung thời gian phân tích */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-bold text-[#001735] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-[#3D6187]">date_range</span>
                    Khung thời gian phân tích (Horizon)
                  </label>
                  <span className="text-[11px] text-[#68788C]">Khuyến nghị: Trung hạn</span>
                </div>
                <div className="grid grid-cols-3 gap-2 p-1 bg-[#EEF4FF] rounded-lg border border-[#C4C6CF]/40">
                  <button 
                    onClick={() => setHorizon('short')}
                    className={`py-1.5 px-2 rounded-md text-xs transition-all text-center cursor-pointer ${
                      horizon === 'short'
                        ? 'bg-white text-[#001735] font-semibold shadow-xs border border-[#C4C6CF]/40'
                        : 'text-[#3D6187] hover:text-[#001735]'
                    }`}
                  >
                    Ngắn hạn <span className="block text-[10px] text-[#74777F]">1 - 3 tháng</span>
                  </button>
                  <button 
                    onClick={() => setHorizon('medium')}
                    className={`py-1.5 px-2 rounded-md text-xs transition-all text-center cursor-pointer ${
                      horizon === 'medium'
                        ? 'bg-white text-[#001735] font-semibold shadow-xs border border-[#C4C6CF]/40'
                        : 'text-[#3D6187] hover:text-[#001735]'
                    }`}
                  >
                    Trung hạn <span className="block text-[10px] text-[#188253] font-medium">6 - 12T (Mặc định)</span>
                  </button>
                  <button 
                    onClick={() => setHorizon('long')}
                    className={`py-1.5 px-2 rounded-md text-xs transition-all text-center cursor-pointer ${
                      horizon === 'long'
                        ? 'bg-white text-[#001735] font-semibold shadow-xs border border-[#C4C6CF]/40'
                        : 'text-[#3D6187] hover:text-[#001735]'
                    }`}
                  >
                    Dài hạn <span className="block text-[10px] text-[#74777F]">&gt; 1 năm</span>
                  </button>
                </div>
              </div>

              {/* Parameter 2: Ngôn ngữ & Quy mô */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#001735] mb-2">Ngôn ngữ báo cáo</label>
                  <div className="flex items-center gap-1 p-1 bg-[#EEF4FF] rounded-lg border border-[#C4C6CF]/40">
                    <button 
                      onClick={() => setLanguage('vi')}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-semibold cursor-pointer ${
                        language === 'vi'
                          ? 'bg-white shadow-xs text-[#001735] border border-[#C4C6CF]/30'
                          : 'text-[#3D6187] hover:text-[#001735]'
                      }`}
                    >
                      <span className="text-xs">🇻🇳</span> Tiếng Việt
                    </button>
                    <button 
                      onClick={() => setLanguage('en')}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-semibold cursor-pointer ${
                        language === 'en'
                          ? 'bg-white shadow-xs text-[#001735] border border-[#C4C6CF]/30'
                          : 'text-[#3D6187] hover:text-[#001735]'
                      }`}
                    >
                      <span className="text-xs">🇺🇸</span> English
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#001735] mb-2">Quy mô tài liệu</label>
                  <select 
                    value={docScope}
                    onChange={(e) => setDocScope(e.target.value)}
                    className="w-full bg-[#EEF4FF] border border-[#C4C6CF]/40 rounded-lg text-xs font-medium text-[#001735] py-2 px-3 focus:outline-none focus:ring-2 focus:ring-[#3D6187]/30"
                  >
                    <option>Chuyên sâu (12 trang)</option>
                    <option>Tóm tắt điều hành (3 trang)</option>
                    <option>Tờ tổng kết một trang (One-pager)</option>
                  </select>
                </div>
              </div>

              {/* Parameter 3: Checklist Phân mục báo cáo */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-bold text-[#001735] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-[#3D6187]">checklist</span>
                    Mục nội dung thẩm định ({sections.filter(s => s.checked).length}/6 được chọn)
                  </label>
                  <button 
                    onClick={() => setSections(prev => prev.map(s => ({ ...s, checked: true })))}
                    className="text-[11px] text-[#3D6187] hover:text-[#001735] underline cursor-pointer"
                  >
                    Đặt lại chuẩn
                  </button>
                </div>

                <div className="space-y-2 border border-[#E1E7EF] rounded-xl p-2.5 bg-white">
                  {sections.map((sec) => (
                    <div 
                      key={sec.id}
                      onClick={() => toggleSection(sec.id)}
                      className={`flex items-center justify-between p-2 rounded-lg border transition-all cursor-pointer ${
                        sec.checked
                          ? 'bg-[#EEF4FF]/70 border-[#E1E7EF]'
                          : 'bg-white border-[#E1E7EF]/50 opacity-60 hover:opacity-100'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-[18px] text-[#68788C] cursor-grab">
                          drag_indicator
                        </span>
                        <input 
                          type="checkbox" 
                          checked={sec.checked}
                          onChange={() => {}}
                          className="w-4 h-4 rounded text-[#001735] focus:ring-[#001735] border-[#C4C6CF]"
                        />
                        <div>
                          <p className="text-xs font-semibold text-[#001735]">{sec.title}</p>
                          <p className="text-[11px] text-[#68788C]">{sec.sub}</p>
                        </div>
                      </div>
                      <span className="text-[11px] font-semibold text-[#3D6187] bg-[#E4EFFF] px-2 py-0.5 rounded flex-shrink-0">
                        {sec.pages}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Parameter 4: Generation Status & Multi-State Feedback Widget */}
              <div className="border border-[#C4C6CF]/40 rounded-xl p-4 bg-[#EEF4FF]/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#3D6187] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-[#188253]">sync_saved_locally</span>
                    Trạng thái kết xuất dữ liệu
                  </span>
                  <span className={`text-xs font-semibold flex items-center gap-1 ${
                    generationState === 'ready' 
                      ? 'text-[#188253]' 
                      : generationState === 'generating' 
                      ? 'text-[#B7791F]' 
                      : 'text-[#C04B4B]'
                  }`}>
                    <span className={`w-2 h-2 rounded-full ${
                      generationState === 'ready' 
                        ? 'bg-[#188253]' 
                        : generationState === 'generating' 
                        ? 'bg-[#B7791F] animate-ping' 
                        : 'bg-[#C04B4B]'
                    }`}></span>
                    {generationState === 'ready' ? 'Hoàn tất 100%' : generationState === 'generating' ? 'Đang tạo 68%' : 'Lỗi kết nối'}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="space-y-1.5">
                  <div className="w-full h-2 bg-[#E4EFFF] rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${
                        generationState === 'ready' ? 'bg-[#001735] w-full' : generationState === 'generating' ? 'bg-[#3D6187] w-[68%]' : 'bg-[#C04B4B] w-[30%]'
                      }`}
                    ></div>
                  </div>
                  <div className="flex justify-between text-[11px] text-[#44474E]">
                    <span>
                      {generationState === 'ready' 
                        ? 'Tổng hợp dữ liệu & Biên soạn: Đã hoàn tất' 
                        : generationState === 'generating' 
                        ? 'Đang tính toán mô hình định giá DCF...' 
                        : 'Không thể kết nối máy chủ'}
                    </span>
                    <span className="font-semibold text-[#001735]">
                      {generationState === 'ready' ? 'PDF Sẵn sàng (4.2 MB)' : 'Chờ xử lý'}
                    </span>
                  </div>
                </div>

                {/* Quick State Switcher / Feedback Demo */}
                <div className="pt-2 border-t border-[#E1E7EF] flex items-center justify-between text-xs">
                  <span className="text-[#68788C] text-[11px]">Mô phỏng trạng thái:</span>
                  <div className="flex items-center gap-1.5">
                    <button 
                      onClick={() => setGenerationState('ready')}
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold cursor-pointer ${
                        generationState === 'ready' ? 'bg-[#E6F4EC] text-[#188253] ring-1 ring-[#188253]/30' : 'bg-white text-[#68788C]'
                      }`}
                    >
                      Sẵn sàng
                    </button>
                    <button 
                      onClick={() => setGenerationState('generating')}
                      className={`px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer ${
                        generationState === 'generating' ? 'bg-[#FFF4D8] text-[#B7791F] ring-1 ring-[#B7791F]/30' : 'bg-white text-[#68788C]'
                      }`}
                    >
                      Đang tạo (68%)
                    </button>
                    <button 
                      onClick={() => setGenerationState('error')}
                      className={`px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer ${
                        generationState === 'error' ? 'bg-[#FCEBEC] text-[#C04B4B] ring-1 ring-[#C04B4B]/30' : 'bg-white text-[#68788C]'
                      }`}
                    >
                      Thử lại API
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Action Strip */}
            <div className="p-5 sm:p-6 bg-white border-t border-[#E1E7EF] space-y-2.5 flex-none">
              <button 
                onClick={handleDownload}
                disabled={downloading}
                className="w-full py-3 px-4 rounded-lg bg-[#1A56DB] hover:bg-[#1D4ED8] text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 shadow-sm transition-all active:scale-[0.99] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {downloading ? 'sync' : 'file_download'}
                </span>
                <span>
                  {downloading ? 'Đang chuẩn bị bản in / PDF...' : `Tải xuống Báo cáo PDF (PDF - 4.2 MB)`}
                </span>
              </button>

              <div className="grid grid-cols-2 gap-2">
                <button 
                  onClick={handleCopyLink}
                  className="py-2 px-3 rounded-lg border border-[#BFDBFE] text-[#1A56DB] hover:bg-[#EFF6FF] text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px]">link</span>
                  <span>{copiedLink ? 'Đã sao chép link!' : 'Sao chép Liên kết'}</span>
                </button>
                <button 
                  onClick={handleSendEmail}
                  className="py-2 px-3 rounded-lg border border-[#BFDBFE] text-[#1A56DB] hover:bg-[#EFF6FF] text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px]">mail</span>
                  <span>{emailSent ? 'Đã gửi qua email!' : 'Gửi qua Email'}</span>
                </button>
              </div>
            </div>
          </section>

          {/* ================= RIGHT PANEL: INTERACTIVE PDF VIEWER PREVIEW (7 Cols) ================= */}
          <section className="pdf-export-preview col-span-12 lg:col-span-7 bg-[#EDF3FC] flex flex-col overflow-hidden">
            
            {/* PDF Viewer Toolbar */}
            <div className="pdf-export-toolbar h-12 bg-white border-b border-[#C4C6CF]/40 px-4 flex items-center justify-between flex-none text-[#3D6187]">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 text-xs">
                  <button 
                    disabled={activePage <= 1}
                    onClick={() => setActivePage(p => Math.max(1, p - 1))}
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#EEF4FF] transition-colors disabled:opacity-40 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                  </button>
                  <span className="text-[#001735] font-semibold">{activePage}</span>
                  <span>/</span>
                  <span>12</span>
                  <button 
                    disabled={activePage >= 12}
                    onClick={() => setActivePage(p => Math.min(12, p + 1))}
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#EEF4FF] transition-colors disabled:opacity-40 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                  </button>
                </div>

                <div className="h-4 w-px bg-[#C4C6CF]/50"></div>

                {/* Zoom Tools */}
                <div className="flex items-center gap-1.5">
                  <button 
                    onClick={() => setZoomLevel(z => Math.max(60, z - 10))}
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#EEF4FF] cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">remove</span>
                  </button>
                  <span className="text-xs font-semibold px-1 text-[#0C1D2D] font-mono-numbers">{zoomLevel}%</span>
                  <button 
                    onClick={() => setZoomLevel(z => Math.min(140, z + 10))}
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#EEF4FF] cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">add</span>
                  </button>
                  <button 
                    onClick={() => setZoomLevel(100)}
                    className="px-2 py-1 text-xs hover:bg-[#EEF4FF] rounded cursor-pointer font-medium"
                  >
                    Fit Width
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Watermark Toggle */}
                <button
                  onClick={() => setWatermarkEnabled(!watermarkEnabled)}
                  className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#EEF4FF] border border-[#C4C6CF]/40 text-xs cursor-pointer hover:bg-[#E4EFFF]"
                >
                  <span className="material-symbols-outlined text-[16px] text-[#3D6187]">branding_watermark</span>
                  <span className="text-[11px] font-medium text-[#001735]">Watermark Pro</span>
                  <span className={`w-2 h-2 rounded-full ${watermarkEnabled ? 'bg-[#188253]' : 'bg-[#C4C6CF]'}`}></span>
                </button>

                <div className="h-4 w-px bg-[#C4C6CF]/50 mx-1"></div>

                <button 
                  onClick={handlePrint}
                  className="w-8 h-8 flex items-center justify-center rounded hover:bg-[#EEF4FF] text-[#3D6187] hover:text-[#001735] cursor-pointer"
                  title="In tài liệu"
                >
                  <span className="material-symbols-outlined text-[18px]">print</span>
                </button>
                <button 
                  onClick={handleDownload}
                  className="w-8 h-8 flex items-center justify-center rounded hover:bg-[#EEF4FF] text-[#3D6187] hover:text-[#001735] cursor-pointer"
                  title="Tải tệp PDF"
                >
                  <span className="material-symbols-outlined text-[18px]">download</span>
                </button>
              </div>
            </div>

            {/* Document Render Surface (High-Fidelity Equity Research Page 1 / 2) */}
            <div className="pdf-report-surface flex-1 overflow-y-auto custom-scrollbar p-4 sm:p-6 flex justify-center bg-[#CBDBF2]/40">
              {(isPrinting ? Array.from({ length: 12 }, (_, index) => index + 1) : [activePage]).map(page => (
              <div 
                key={page}
                style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'top center' }}
                className="pdf-report-document w-full max-w-[620px] bg-white shadow-xl rounded-xs border border-[#C4C6CF]/40 p-7 sm:p-8 flex flex-col justify-between min-h-[820px] relative transition-transform duration-150"
              >
                {/* Security Watermark */}
                {watermarkEnabled && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.035] select-none rotate-[-30deg]">
                    <span className="text-6xl font-extrabold tracking-widest text-[#001735] uppercase text-center">
                      STOCKLENS PRO RESEARCH
                    </span>
                  </div>
                )}

                {/* Page Content Rendering based on activePage */}
                {page === 1 ? (
                  <div className="space-y-4 relative z-10">
                    {/* Header */}
                    <div className="border-b-2 border-[#1A56DB] pb-3.5">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded bg-[#1A56DB] text-white flex items-center justify-center font-bold text-xs">
                            SL
                          </div>
                          <span className="text-xs font-bold tracking-tight text-[#1A56DB]">
                            STOCKLENS INSTITUTIONAL RESEARCH
                          </span>
                        </div>
                        <span className="text-[10px] text-[#68788C] font-mono-numbers">
                          BÁO CÁO CẬP NHẬT | 24/10/2024
                        </span>
                      </div>

                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <CompanyLogo symbol={stock.symbol} size="lg" className="flex-shrink-0" />
                          <div>
                            <h2 className="text-base sm:text-lg font-bold text-[#0C1D2D] tracking-tight">
                              {stock.name.toUpperCase()} (HOSE: {stock.symbol})
                            </h2>
                            <p className="text-xs text-[#68788C] font-medium">
                              {stock.companyOverview.marketPosition}
                            </p>
                          </div>
                        </div>
                        {/* Target & Recommendation */}
                        <div className="text-right flex-shrink-0">
                          <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#E6F4EC] text-[#188253] border border-[#188253]/30 inline-block">
                            {stock.aiRecommendation}
                          </span>
                          <div className="mt-1 text-right">
                            <span className="text-xs text-[#68788C] block">
                              Giá mục tiêu: <strong className="text-[#1A56DB] font-bold font-mono-numbers">{stock.targetPrice.toLocaleString('vi-VN')} đ</strong>
                            </span>
                            <span className="text-[11px] text-[#188253] font-semibold font-mono-numbers">
                              +{stock.upside}% Upside (Giá: {stock.currentPrice.toLocaleString('vi-VN')} đ)
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Executive Summary & AI Rating Box */}
                    <div className="bg-[#EFF6FF] border-l-4 border-[#1A56DB] rounded-r-lg p-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase text-[#001735] tracking-wider flex items-center gap-1.5">
                          <span className="material-symbols-outlined text-[15px] text-[#3D6187]">psychology</span>
                          Tóm tắt điều hành & Điểm số AI StockLens
                        </span>
                        <span className="text-[11px] px-2 py-0.5 rounded bg-white font-bold text-[#001735] border border-[#C4C6CF]/40">
                          Điểm AI: <span className="text-[#188253] font-mono-numbers">{stock.aiScore} / 100</span>
                        </span>
                      </div>
                      <p className="text-[11px] text-[#0C1D2D] leading-relaxed">
                        {stock.symbol} duy trì đà tăng trưởng hai con số bền vững nhờ mảng Xuất khẩu Phần mềm (DX) bứt phá tại Nhật Bản (+34% YoY) và thị trường Mỹ. Chiến lược tích hợp AI Factory và hợp tác chiến lược cùng NVIDIA định vị doanh nghiệp như hạt nhân công nghệ cao của khu vực ASEAN.
                      </p>
                    </div>

                    {/* Key Financial Metrics Table */}
                    <div>
                      <h3 className="text-[11px] font-bold uppercase tracking-wider text-[#68788C] mb-1.5">
                        Chỉ số tài chính trọng yếu (2022 - 2025F)
                      </h3>
                      <div className="border border-[#C4C6CF]/40 rounded-lg overflow-hidden text-[11px]">
                        <table className="w-full text-left">
                          <thead className="bg-[#EEF4FF] text-[#68788C] font-semibold border-b border-[#C4C6CF]/30">
                            <tr>
                              <th className="py-1.5 px-2.5">Chỉ tiêu (Tỷ VNĐ)</th>
                              {stock.financials.years.map((y, i) => (
                                <th key={i} className={`py-1.5 px-2 text-right ${i >= 2 ? 'font-bold text-[#001735]' : ''}`}>
                                  {y}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#E1E7EF]/60 font-mono-numbers text-[11px]">
                            <tr className="hover:bg-[#EEF4FF]/40">
                              <td className="py-1 px-2.5 font-medium text-[#001735] font-sans">Doanh thu thuần</td>
                              {stock.financials.revenue.map((val, idx) => (
                                <td key={idx} className="py-1 px-2 text-right text-[#0C1D2D]">
                                  {val.toLocaleString('vi-VN')}
                                </td>
                              ))}
                            </tr>
                            <tr className="hover:bg-[#EEF4FF]/40">
                              <td className="py-1 px-2.5 font-medium text-[#001735] font-sans">Lợi nhuận sau thuế</td>
                              {stock.financials.netIncome.map((val, idx) => (
                                <td key={idx} className="py-1 px-2 text-right font-bold text-[#188253]">
                                  {val.toLocaleString('vi-VN')}
                                </td>
                              ))}
                            </tr>
                            <tr className="hover:bg-[#EEF4FF]/40">
                              <td className="py-1 px-2.5 font-medium text-[#001735] font-sans">EPS điều chỉnh (VND)</td>
                              {stock.financials.eps.map((val, idx) => (
                                <td key={idx} className="py-1 px-2 text-right text-[#0C1D2D]">
                                  {val.toLocaleString('vi-VN')}
                                </td>
                              ))}
                            </tr>
                            <tr className="hover:bg-[#EEF4FF]/40">
                              <td className="py-1 px-2.5 font-medium text-[#001735] font-sans">P/E dự phóng (x)</td>
                              {stock.financials.peProj.map((val, idx) => (
                                <td key={idx} className="py-1 px-2 text-right text-[#0C1D2D]">
                                  {val}
                                </td>
                              ))}
                            </tr>
                            <tr className="hover:bg-[#EEF4FF]/40 bg-[#EEF4FF]/20">
                              <td className="py-1 px-2.5 font-medium text-[#001735] font-sans">ROE (%)</td>
                              {stock.financials.roeProj.map((val, idx) => (
                                <td key={idx} className="py-1 px-2 text-right font-bold text-[#188253]">
                                  {val}
                                </td>
                              ))}
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Dual Visual Mini-Panels */}
                    <div className="grid grid-cols-2 gap-3">
                      {/* Revenue breakdown */}
                      <div className="p-2.5 rounded-lg border border-[#C4C6CF]/40 bg-[#EEF4FF]/30">
                        <span className="text-[11px] font-bold text-[#001735] block mb-2">
                          Cơ cấu Doanh thu theo khối
                        </span>
                        <div className="space-y-1.5">
                          {stock.revenueBreakdown.map((item, idx) => (
                            <div key={idx}>
                              <div className="flex justify-between text-[10px] mb-0.5">
                                <span className="text-[#68788C]">{item.name}</span>
                                <span className="font-bold text-[#001735] font-mono-numbers">{item.share}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-[#E4EFFF] rounded-full overflow-hidden">
                                <div 
                                  className="h-full rounded-full" 
                                  style={{ width: `${item.share}%`, backgroundColor: item.color }}
                                ></div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* SVG Mini Chart */}
                      <div className="p-2.5 rounded-lg border border-[#C4C6CF]/40 bg-[#EEF4FF]/30 flex flex-col justify-between">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-[11px] font-bold text-[#001735]">Diễn biến giá vs VN-Index</span>
                          <span className="text-[10px] text-[#188253] font-bold font-mono-numbers">+41.2% YTD</span>
                        </div>
                        <div className="h-10 w-full pt-1">
                          <svg className="w-full h-full overflow-visible" viewBox="0 0 200 45">
                            <polyline
                              fill="none"
                              points="0,38 30,35 60,32 90,34 120,30 150,28 180,26 200,24"
                              stroke="#C4C6CF"
                              strokeDasharray="2,2"
                              strokeWidth="1.5"
                            />
                            <polyline
                              fill="none"
                              points="0,40 30,36 60,30 90,26 120,20 150,14 180,9 200,4"
                              stroke="#001735"
                              strokeWidth="2.2"
                            />
                            <circle cx="200" cy="4" fill="#188253" r="3" />
                          </svg>
                        </div>
                        <div className="flex justify-between text-[9px] text-[#68788C] font-mono-numbers">
                          <span>T1/2024</span>
                          <span>FPT (Xanh đậm) vs VNINDEX (Đứt)</span>
                          <span>Hôm nay</span>
                        </div>
                      </div>
                    </div>

                    {/* Key Investment Thesis */}
                    <div className="space-y-1">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[#68788C] block">
                        Luận điểm đầu tư then chốt
                      </span>
                      <ul className="text-[11px] text-[#0C1D2D] space-y-1 pl-4 list-disc">
                        <li>
                          <strong>Động lực chuyển đổi số toàn cầu:</strong> Doanh thu ký mới đạt 1.2 tỷ USD, duy trì tăng trưởng kép CAGR 26% trong giai đoạn 2024-2027.
                        </li>
                        <li>
                          <strong>Bảo chứng tài chính lành mạnh:</strong> Tỷ lệ tiền ròng trên vốn chủ sở hữu cao, chi trả cổ tức tiền mặt đều đặn 20% mỗi năm.
                        </li>
                        <li>
                          <strong>Định giá hợp lý:</strong> P/E 19.2x là mức hấp dẫn đối với doanh nghiệp công nghệ có ROE vượt trội 28.4% và tăng trưởng EPS trên 24%.
                        </li>
                      </ul>
                    </div>
                  </div>
                ) : (
                  /* Secondary Pages Preview */
                  <div className="space-y-4 relative z-10 py-4">
                    <div className="border-b border-[#001735] pb-2">
                      <span className="text-[10px] text-[#68788C] uppercase font-bold tracking-wider">
                        Phân mục {page} / 12
                      </span>
                      <h2 className="text-base font-bold text-[#001735]">
                        {page === 2 && 'Mô Hình Định Giá DCF & Bảng Nhạy Cảm WACC/g'}
                        {page === 3 && 'Phân Tích Cơ Cấu Nợ & Khả Năng Sinh Lời ROE Du-Pont'}
                        {page >= 4 && `Thẩm Định Chuyên Sâu Phần ${page}: Dòng Tiền & Rủi Ro`}
                      </h2>
                    </div>

                    <div className="p-4 rounded-lg bg-[#EEF4FF] border border-[#C4C6CF]/40 text-xs text-[#0C1D2D] space-y-3">
                      <p>
                        <strong>Tóm tắt phương pháp:</strong> Định giá dòng tiền tự do doanh nghiệp (FCFF) với tỷ suất chiết khấu WACC 10.8%, tốc độ tăng trưởng vĩnh viễn g = 3.5%. Giá trị hợp lý của mỗi cổ phần {stock.symbol} ước tính đạt <strong>{stock.targetPrice.toLocaleString('vi-VN')} VND</strong>.
                      </p>
                      <div className="grid grid-cols-3 gap-2 p-2 bg-white rounded border border-[#E1E7EF] font-mono-numbers text-[11px]">
                        <div>WACC: 10.8%</div>
                        <div>Beta: 0.88</div>
                        <div>Tăng trưởng g: 3.5%</div>
                      </div>
                      <p className="text-[11px] text-[#44474E]">
                        Biên độ an toàn hiện hữu là {stock.marginOfSafety}, mang lại tỷ suất lợi nhuận kỳ vọng hấp dẫn trên góc nhìn trung và dài hạn.
                      </p>
                    </div>
                  </div>
                )}

                {/* Footer Metadata */}
                <div className="pdf-report-footer pt-3 mt-4 border-t border-[#E1E7EF] text-[9px] text-[#68788C] flex items-end justify-between font-mono-numbers relative z-10">
                  <div className="space-y-0.5">
                    <p>Mã tài liệu: <strong>SL-EQ-2024-{stock.symbol}-Q3</strong> | Nguồn: HOSE, PwC Audit, StockLens AI v4.2</p>
                    <p>Checksum: SHA256-4f8a91c80b27e411bfa3c6759c21 | Thẩm định viên: <strong>Trần Minh Quang, CFA</strong></p>
                  </div>
                  <div className="text-right">
                    <span className="font-bold text-[#001735]">Trang {page} / 12</span>
                  </div>
                </div>
              </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

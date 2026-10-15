import React, { useState } from 'react';
import { StockData } from '../data/stocks';
import { CompanyLogo } from './CompanyLogo';

interface OverviewViewProps {
  stock: StockData;
  onNavigateTab: (tab: any) => void;
  onOpenPdfModal: () => void;
  onOpenCompanyProfile?: () => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  stock,
  onNavigateTab,
  onOpenCompanyProfile,
}) => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1M');
  const [hoveredCandle, setHoveredCandle] = useState<number | null>(null);

  const timeframes = ['1D', '1W', '1M', '3M', '1Y', 'ALL'];

  // Calculate 52W range slider percentage
  const rangeMin = stock.low52w;
  const rangeMax = Math.max(stock.targetPrice * 1.05, stock.high52w);
  const currentPct = Math.min(100, Math.max(0, ((stock.currentPrice - rangeMin) / (rangeMax - rangeMin)) * 100));
  const targetPct = Math.min(100, Math.max(0, ((stock.targetPrice - rangeMin) / (rangeMax - rangeMin)) * 100));

  return (
    <div className="space-y-4">
      {/* ================= COMPANY BRIEF OVERVIEW BANNER ================= */}
      <div className="bg-gradient-to-r from-[#EFF6FF] to-[#DBEAFE]/40 rounded-xl border border-[#BFDBFE] p-4 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <CompanyLogo symbol={stock.symbol} size="lg" className="flex-shrink-0" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-bold text-[#1E3A8A]">Hồ Sơ Doanh Nghiệp: {stock.name}</h3>
              <span className="text-[10px] font-bold text-[#1A56DB] bg-white px-2 py-0.5 rounded border border-[#BFDBFE]">
                Thành lập {stock.companyOverview.foundingYear}
              </span>
              <span className="text-[11px] text-[#1E40AF] font-medium hidden sm:inline">
                • {stock.companyOverview.marketPosition}
              </span>
            </div>
            <p className="text-xs text-[#1E40AF] mt-1 line-clamp-2 leading-relaxed">
              {stock.companyOverview.shortDescription}
            </p>
          </div>
        </div>

        {onOpenCompanyProfile && (
          <button
            onClick={onOpenCompanyProfile}
            className="self-start md:self-auto px-3.5 py-2 rounded-lg bg-[#1A56DB] hover:bg-[#1D4ED8] text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-xs cursor-pointer flex-shrink-0"
          >
            <span>Xem chi tiết hồ sơ</span>
            <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
          </button>
        )}
      </div>

      {/* ================= TOP 3 STRATEGIC METRIC CARDS ================= */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CARD 1: Giá thị trường hiện tại */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-[#1A56DB] flex items-center gap-1.5 uppercase tracking-wide">
                <span className="w-2 h-2 rounded-full bg-[#188253] animate-pulse"></span>
                GIÁ THỊ TRƯỜNG HIỆN TẠI
              </span>
              <span className="text-[11px] font-medium text-[#1A56DB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                Phiên Khớp lệnh liên tục
              </span>
            </div>

            <div className="flex items-baseline gap-3 my-1">
              <span className="text-2xl sm:text-3xl font-extrabold text-[#0C1D2D] tracking-tight font-mono-numbers">
                {stock.currentPrice.toLocaleString('vi-VN')}
              </span>
              <span className="text-xs font-semibold text-[#68788C]">VND</span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#E6F4EC] text-[#188253] border border-[#188253]/20 font-mono-numbers">
                <span className="material-symbols-outlined text-[14px]">arrow_upward</span>
                +{stock.priceChange.toLocaleString('vi-VN')} (+{stock.priceChangePercent}%)
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 py-3 border-y border-[#E1E7EF]/70 my-2 text-xs">
              <div>
                <span className="text-[11px] text-[#68788C] block">Khối lượng:</span>
                <span className="font-bold text-[#0C1D2D] font-mono-numbers text-[12px]">
                  {stock.volume.toLocaleString('vi-VN')} CP
                </span>
              </div>
              <div>
                <span className="text-[11px] text-[#68788C] block">Tham chiếu:</span>
                <span className="font-bold text-[#0C1D2D] font-mono-numbers text-[12px]">
                  {stock.refPrice.toLocaleString('vi-VN')}
                </span>
              </div>
              <div>
                <span className="text-[11px] text-[#68788C] block">Cao / Thấp:</span>
                <span className="font-bold text-[#0C1D2D] font-mono-numbers text-[12px]">
                  {(stock.highPrice / 1000).toFixed(1)} / {(stock.lowPrice / 1000).toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] text-[#68788C] pt-1">
            <span>
              So với TB 20 phiên: <strong className="text-[#188253] font-semibold">{stock.avg20dComparison}</strong>
            </span>
            <span className="font-mono-numbers text-[#74777F]">{stock.tradingTime}</span>
          </div>
        </div>

        {/* CARD 2: Khuyến nghị đầu tư AI */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#E6F4EC] rounded-full blur-2xl pointer-events-none opacity-60"></div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-[#6B46C1] flex items-center gap-1.5 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[16px] text-[#6B46C1]">psychology</span>
                KHUYẾN NGHỊ ĐẦU TƯ AI
              </span>
              <span className="text-[10px] font-bold text-white bg-[#005231] px-2 py-0.5 rounded tracking-wider">
                {stock.aiModelVersion}
              </span>
            </div>

            <div className="flex items-center gap-3 my-1.5">
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold bg-[#E6F4EC] text-[#188253] border border-[#188253]/30">
                <span className="material-symbols-outlined text-[15px]">verified</span>
                {stock.aiRecommendation}
              </span>
              <div className="px-3 py-1 rounded-lg bg-[#00331D] text-white text-xs font-bold flex items-center gap-1">
                <span>ĐIỂM:</span>
                <span className="text-[#96F6BD] text-sm font-extrabold font-mono-numbers">{stock.aiScore}</span>
                <span className="text-white/70 text-[10px]">/100</span>
              </div>
            </div>

            <p className="text-xs text-[#44474E] leading-relaxed my-2 line-clamp-2">
              {stock.aiThesis}
            </p>
          </div>

          <div className="flex items-center justify-between text-[11px] pt-2 border-t border-[#E1E7EF]/70">
            <span className="text-[#68788C]">
              Độ tin cậy mô hình: <strong className="text-[#0C1D2D] font-bold font-mono-numbers">{stock.aiConfidence}</strong>
            </span>
            <button
              onClick={() => onNavigateTab('bullbear')}
              className="text-[#188253] font-bold hover:underline flex items-center gap-0.5 cursor-pointer"
            >
              <span>Xem Luận Điểm Chi Tiết</span>
              <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </button>
          </div>
        </div>

        {/* CARD 3: Giá mục tiêu & Kỳ vọng (12M) */}
        <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-[#1A56DB] flex items-center gap-1.5 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[16px] text-[#1A56DB]">flag</span>
                GIÁ MỤC TIÊU & KỲ VỌNG (12M)
              </span>
              <span className="text-[10px] font-semibold text-[#6B46C1] bg-[#F0E7FC] px-2 py-0.5 rounded border border-[#6B46C1]/30">
                {stock.valuationMethod}
              </span>
            </div>

            <div className="flex items-baseline gap-3 my-1">
              <span className="text-2xl sm:text-3xl font-extrabold text-[#0C1D2D] tracking-tight font-mono-numbers">
                {stock.targetPrice.toLocaleString('vi-VN')}
              </span>
              <span className="text-xs font-semibold text-[#68788C]">VND</span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#E6F4EC] text-[#188253] border border-[#188253]/20 font-mono-numbers">
                <span className="material-symbols-outlined text-[14px]">trending_up</span>
                Upside +{stock.upside}%
              </span>
            </div>

            {/* Range visualization slider */}
            <div className="my-3 space-y-1.5">
              <div className="flex justify-between text-[11px] font-mono-numbers text-[#68788C]">
                <span>Đáy 52W: {stock.low52w.toLocaleString('vi-VN')}</span>
                <span className="font-bold text-[#0C1D2D]">Hiện tại: {(stock.currentPrice / 1000).toFixed(0)},500</span>
                <span className="font-bold text-[#188253]">Target: {stock.targetPrice.toLocaleString('vi-VN')}</span>
              </div>
              <div className="relative h-2 bg-[#E4EFFF] rounded-full overflow-hidden">
                <div 
                  className="absolute top-0 bottom-0 left-0 bg-[#3D6187]/40 rounded-full"
                  style={{ width: `${currentPct}%` }}
                ></div>
                <div 
                  className="absolute top-0 bottom-0 bg-[#188253]/50 rounded-full"
                  style={{ left: `${currentPct}%`, width: `${Math.max(0, targetPct - currentPct)}%` }}
                ></div>
                {/* Marker at current price in bright blue */}
                <div 
                  className="absolute top-0 bottom-0 w-2 bg-[#1A56DB] rounded-full shadow-xs"
                  style={{ left: `calc(${currentPct}% - 4px)` }}
                ></div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] text-[#68788C] pt-1 border-t border-[#E1E7EF]/70">
            <span>
              Biên độ an toàn (Margin of Safety): <strong className="text-[#0C1D2D] font-bold font-mono-numbers">{stock.marginOfSafety}</strong>
            </span>
            <span className="font-medium text-[#1A56DB]">{stock.consensusBrokers}</span>
          </div>
        </div>
      </div>

      {/* ================= MULTI-FACTOR QUANTITATIVE PIPELINE ================= */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3.5 mb-3.5 border-b border-[#E1E7EF] gap-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] flex items-center justify-center text-[#1A56DB]">
              <span className="material-symbols-outlined text-[18px]">hub</span>
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0C1D2D]">
                Mô Hình Đánh Giá Đa Nhân Tố (StockLens Multi-Factor Pipeline)
              </h2>
              <p className="text-[11px] text-[#68788C]">
                • Trọng số định lượng chu kỳ 2024 - 2025
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <span className="text-xs text-[#68788C] font-medium">Điểm tổng hợp lượng hóa:</span>
            <span className="px-3 py-1 rounded-lg bg-[#1A56DB] text-white font-mono-numbers font-extrabold text-sm tracking-wide shadow-xs">
              {stock.aiScore} / 100
            </span>
          </div>
        </div>

        {/* 5 Factors Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Factor 1: F Cơ bản */}
          <div className="bg-[#F8F9FF] rounded-xl border border-[#E1E7EF] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-[#0C1D2D] flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded bg-[#1A56DB] text-white flex items-center justify-center text-[10px] font-bold">
                    F
                  </span>
                  Cơ bản
                </span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  {stock.factors.fFundamental.score}/100
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#E1E7EF] rounded-full overflow-hidden mb-2">
                <div 
                  className="h-full bg-[#188253] rounded-full" 
                  style={{ width: `${stock.factors.fFundamental.score}%` }}
                ></div>
              </div>
            </div>
            <p className="text-[11px] text-[#44474E] leading-relaxed">
              {stock.factors.fFundamental.text}
            </p>
          </div>

          {/* Factor 2: T Kỹ thuật */}
          <div className="bg-[#F8F9FF] rounded-xl border border-[#E1E7EF] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-[#0C1D2D] flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded bg-[#1A56DB] text-white flex items-center justify-center text-[10px] font-bold">
                    T
                  </span>
                  Kỹ thuật
                </span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  {stock.factors.tTechnical.score}/100
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#E1E7EF] rounded-full overflow-hidden mb-2">
                <div 
                  className="h-full bg-[#188253] rounded-full" 
                  style={{ width: `${stock.factors.tTechnical.score}%` }}
                ></div>
              </div>
            </div>
            <p className="text-[11px] text-[#44474E] leading-relaxed">
              {stock.factors.tTechnical.text}
            </p>
          </div>

          {/* Factor 3: V Định giá */}
          <div className="bg-[#F8F9FF] rounded-xl border border-[#E1E7EF] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-[#0C1D2D] flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded bg-[#1A56DB] text-white flex items-center justify-center text-[10px] font-bold">
                    V
                  </span>
                  Định giá
                </span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  {stock.factors.vValuation.score}/100
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#E1E7EF] rounded-full overflow-hidden mb-2">
                <div 
                  className="h-full bg-[#188253] rounded-full" 
                  style={{ width: `${stock.factors.vValuation.score}%` }}
                ></div>
              </div>
            </div>
            <p className="text-[11px] text-[#44474E] leading-relaxed">
              {stock.factors.vValuation.text}
            </p>
          </div>

          {/* Factor 4: S Tâm lý & Tin */}
          <div className="bg-[#F8F9FF] rounded-xl border border-[#E1E7EF] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-[#0C1D2D] flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded bg-[#1A56DB] text-white flex items-center justify-center text-[10px] font-bold">
                    S
                  </span>
                  Tâm lý & Tin
                </span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  {stock.factors.sSentiment.score}/100
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#E1E7EF] rounded-full overflow-hidden mb-2">
                <div 
                  className="h-full bg-[#188253] rounded-full" 
                  style={{ width: `${stock.factors.sSentiment.score}%` }}
                ></div>
              </div>
            </div>
            <p className="text-[11px] text-[#44474E] leading-relaxed">
              {stock.factors.sSentiment.text}
            </p>
          </div>

          {/* Factor 5: R Rủi ro trừ điểm */}
          <div className="bg-[#FFF8F8] rounded-xl border border-[#FFDAD6] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-[#BA1A1A] flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded bg-[#BA1A1A] text-white flex items-center justify-center text-[10px] font-bold">
                    R
                  </span>
                  Rủi ro trừ điểm
                </span>
                <span className="text-xs font-bold text-[#BA1A1A] font-mono-numbers">
                  {stock.factors.rRisk.score} điểm
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#FFDAD6] rounded-full overflow-hidden mb-2">
                <div className="h-full bg-[#BA1A1A] rounded-full w-[35%]"></div>
              </div>
            </div>
            <p className="text-[11px] text-[#93000A] leading-relaxed">
              {stock.factors.rRisk.text}
            </p>
          </div>
        </div>
      </div>

      {/* ================= LOWER SPLIT SECTION: CHART & BULL/BEAR/AUDIT ================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT COLUMN: INTERACTIVE CHART & TECHNICAL INDICATORS (7.5 cols) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
            {/* Chart Toolbar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-[#E1E7EF] gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[18px] text-[#3D6187]">show_chart</span>
                  <h3 className="text-xs sm:text-sm font-bold text-[#001735]">
                    Biểu đồ Kỹ thuật Nhật ký Khớp lệnh
                  </h3>
                </div>
                <div className="flex items-center gap-3 text-xs text-[#68788C]">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-[#3D6187]"></span>
                    SMA20: <strong className="text-[#0C1D2D] font-mono-numbers">{stock.sma20}</strong>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-[#B7791F]"></span>
                    SMA50: <strong className="text-[#0C1D2D] font-mono-numbers">{stock.sma50}</strong>
                  </span>
                </div>
              </div>

              {/* Timeframe selector tabs */}
              <div className="flex items-center gap-1 p-0.5 bg-[#EFF6FF] rounded-lg border border-[#BFDBFE] self-start sm:self-auto">
                {timeframes.map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setSelectedTimeframe(tf)}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                      selectedTimeframe === tf
                        ? 'bg-[#1A56DB] text-white shadow-xs'
                        : 'text-[#1A56DB] hover:text-[#1D4ED8]'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            {/* Candlestick & Volume Chart Canvas Area */}
            <div className="relative w-full h-[320px] sm:h-[340px] select-none">
              {/* Guidelines & Annotations */}
              <div className="absolute inset-0 pointer-events-none flex flex-col justify-between py-6">
                {/* Resistance Line R1 */}
                <div className="relative border-b border-dashed border-[#C4C6CF]/80 w-full flex items-center justify-between">
                  <span className="text-[10px] text-[#74777F] font-mono-numbers bg-white pr-2">
                    Kháng Cự R1: {stock.resistanceR1.toFixed(1)}
                  </span>
                  <span className="text-[10px] font-bold text-white bg-[#1A56DB] px-2 py-0.5 rounded shadow-xs font-mono-numbers">
                    {stock.currentPrice.toLocaleString('vi-VN')}
                  </span>
                </div>

                {/* Current Price Line */}
                <div className="relative border-b border-dotted border-[#188253]/60 w-full flex items-center justify-between">
                  <span className="text-[10px] text-[#188253] font-mono-numbers bg-white pr-2 font-semibold">
                    Hiện tại: {(stock.currentPrice / 1000).toFixed(1)}
                  </span>
                  <span className="text-[10px] font-bold text-[#188253] bg-[#E6F4EC] px-2 py-0.5 rounded border border-[#188253]/30 font-mono-numbers">
                    {stock.currentPrice.toLocaleString('vi-VN')}
                  </span>
                </div>

                {/* Support Line S1 */}
                <div className="relative border-b border-dashed border-[#C4C6CF]/80 w-full flex items-center justify-between">
                  <span className="text-[10px] text-[#74777F] font-mono-numbers bg-white pr-2">
                    Hỗ trợ S1: {stock.supportS1.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-[#74777F] font-mono-numbers bg-white pl-2">
                    {stock.supportS1.toLocaleString('vi-VN')},000
                  </span>
                </div>
              </div>

              {/* SVG Candlestick and Volume Visualization */}
              <svg 
                className="w-full h-full" 
                viewBox="0 0 700 320" 
                preserveAspectRatio="none"
              >
                {/* Horizontal grid lines */}
                <line x1="0" y1="60" x2="700" y2="60" stroke="#EEF4FF" strokeWidth="1" />
                <line x1="0" y1="140" x2="700" y2="140" stroke="#EEF4FF" strokeWidth="1" />
                <line x1="0" y1="220" x2="700" y2="220" stroke="#EEF4FF" strokeWidth="1" />

                {/* Candlestick bars rendering */}
                {stock.chartData.map((d, idx) => {
                  const x = 30 + idx * 62;
                  const isUp = d.close >= d.open;
                  const candleColor = isUp ? '#188253' : '#C04B4B';
                  const volColor = isUp ? '#188253' : '#C04B4B';

                  // Price mapping to SVG coordinate (range 128 - 142 -> Y from 220 to 30)
                  const minP = 129;
                  const maxP = 142;
                  const scale = (val: number) => 230 - ((val - minP) / (maxP - minP)) * 190;

                  const yHigh = scale(d.high);
                  const yLow = scale(d.low);
                  const yOpen = scale(d.open);
                  const yClose = scale(d.close);
                  const candleTop = Math.min(yOpen, yClose);
                  const candleHeight = Math.max(3, Math.abs(yOpen - yClose));

                  // Volume mapping (range 0 to 6000000 -> Y from 315 to 255)
                  const volHeight = Math.min(55, Math.max(10, (d.volume / 6000000) * 55));
                  const volY = 315 - volHeight;

                  const isHovered = hoveredCandle === idx;

                  return (
                    <g 
                      key={idx} 
                      className="cursor-pointer"
                      onMouseEnter={() => setHoveredCandle(idx)}
                      onMouseLeave={() => setHoveredCandle(null)}
                    >
                      {/* Hover column backdrop */}
                      {isHovered && (
                        <rect
                          x={x - 24}
                          y="10"
                          width="48"
                          height="305"
                          fill="#EEF4FF"
                          opacity="0.6"
                          rx="4"
                        />
                      )}

                      {/* Candlestick Wick (High to Low line) */}
                      <line
                        x1={x}
                        y1={yHigh}
                        x2={x}
                        y2={yLow}
                        stroke={candleColor}
                        strokeWidth="1.8"
                      />

                      {/* Candlestick Body */}
                      <rect
                        x={x - 6}
                        y={candleTop}
                        width="12"
                        height={candleHeight}
                        fill={candleColor}
                        rx="1"
                      />

                      {/* Volume Bar */}
                      <rect
                        x={x - 5}
                        y={volY}
                        width="10"
                        height={volHeight}
                        fill={volColor}
                        opacity={isHovered ? 0.9 : 0.65}
                        rx="1"
                      />
                    </g>
                  );
                })}
              </svg>

              {/* Hover Tooltip Overlay */}
              {hoveredCandle !== null && stock.chartData[hoveredCandle] && (
                <div 
                  className="absolute top-2 left-4 bg-white/95 backdrop-blur-xs border border-[#C4C6CF] rounded-lg p-2.5 shadow-lg text-[11px] font-mono-numbers z-20 pointer-events-none"
                >
                  <div className="font-bold text-[#001735] mb-1">
                    Phiên: {stock.chartData[hoveredCandle].time}
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[#44474E]">
                    <span>Mở cửa: <strong className="text-[#0C1D2D]">{stock.chartData[hoveredCandle].open.toFixed(1)}k</strong></span>
                    <span>Đóng cửa: <strong className="text-[#188253] font-bold">{stock.chartData[hoveredCandle].close.toFixed(1)}k</strong></span>
                    <span>Cao nhất: <strong className="text-[#0C1D2D]">{stock.chartData[hoveredCandle].high.toFixed(1)}k</strong></span>
                    <span>Thấp nhất: <strong className="text-[#0C1D2D]">{stock.chartData[hoveredCandle].low.toFixed(1)}k</strong></span>
                    <span className="col-span-2 pt-1 border-t border-[#E1E7EF] text-[10px] text-[#68788C]">
                      Khối lượng: {(stock.chartData[hoveredCandle].volume / 1000000).toFixed(2)}M CP
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* 4 Technical Indicators Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-3 mt-3 border-t border-[#E1E7EF]">
              <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                <span className="text-[10px] text-[#68788C] block">RSI (14):</span>
                <span className="text-xs font-bold text-[#001735] font-mono-numbers">
                  {stock.technicalIndicators.rsi.value} ({stock.technicalIndicators.rsi.label})
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                <span className="text-[10px] text-[#68788C] block">MACD (12, 26, 9):</span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  +{stock.technicalIndicators.macd.value} ({stock.technicalIndicators.macd.signal})
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                <span className="text-[10px] text-[#68788C] block">Bollinger Bands:</span>
                <span className="text-xs font-bold text-[#001735]">
                  {stock.technicalIndicators.bollinger.status} ({stock.technicalIndicators.bollinger.upper})
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-[#F8F9FF] border border-[#E1E7EF]">
                <span className="text-[10px] text-[#68788C] block">Khối ngoại Mua ròng:</span>
                <span className="text-xs font-bold text-[#188253] font-mono-numbers">
                  {stock.technicalIndicators.foreignFlow.value}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: BULL VS BEAR CASE & AUDIT PROOF (4.5 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Card 1: TRANH LUẬN: BULL VS BEAR CASE */}
          <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-[#E1E7EF]">
                <span className="text-xs font-bold text-[#1A56DB] flex items-center gap-1.5 uppercase tracking-wide">
                  <span className="material-symbols-outlined text-[16px] text-[#1A56DB]">balance</span>
                  TRANH LUẬN: BULL VS BEAR CASE
                </span>
                <span className="text-[10px] font-semibold text-[#1A56DB] bg-[#EFF6FF] px-2 py-0.5 rounded">
                  Hội đồng phản biện AI
                </span>
              </div>

              {/* Bull Case */}
              <div className="mb-4">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#188253] mb-2">
                  <span className="material-symbols-outlined text-[16px]">check_circle</span>
                  Luận điểm Tích cực (Bull Case)
                </div>
                <ul className="text-xs text-[#44474E] space-y-2 pl-2">
                  {stock.bullCase.map((point, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-[#188253] font-bold">•</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Bear Case */}
              <div className="pt-3 border-t border-[#E1E7EF]/70">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#C04B4B] mb-2">
                  <span className="material-symbols-outlined text-[16px]">cancel</span>
                  Luận điểm Rủi ro (Bear Case)
                </div>
                <ul className="text-xs text-[#44474E] space-y-2 pl-2">
                  {stock.bearCase.map((point, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-[#C04B4B] font-bold">•</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="pt-3 mt-3 border-t border-[#E1E7EF] flex justify-end">
              <button
                onClick={() => onNavigateTab('bullbear')}
                className="text-xs font-semibold text-[#3D6187] hover:text-[#001735] flex items-center gap-1 cursor-pointer"
              >
                <span>Xem phân tích chi tiết & bỏ phiếu</span>
                <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
              </button>
            </div>
          </div>

          {/* Card 2: Chứng Thực Dữ Liệu Kiểm Toán */}
          <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs">
            <div className="flex items-center gap-2 pb-2.5 mb-3 border-b border-[#E1E7EF]">
              <span className="material-symbols-outlined text-[18px] text-[#188253]">verified_user</span>
              <h4 className="text-xs font-bold text-[#1A56DB] uppercase tracking-wide">
                Chứng Thực Dữ Liệu Kiểm Toán
              </h4>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-[#E1E7EF]/60">
                <span className="text-[#68788C]">Đơn vị kiểm toán BCTC:</span>
                <strong className="text-[#0C1D2D] text-right font-medium">{stock.audit.auditor}</strong>
              </div>
              <div className="flex justify-between py-1 border-b border-[#E1E7EF]/60">
                <span className="text-[#68788C]">Nguồn cấp dữ liệu:</span>
                <strong className="text-[#0C1D2D] text-right font-medium">{stock.audit.dataSource}</strong>
              </div>
              <div className="flex justify-between py-1 border-b border-[#E1E7EF]/60">
                <span className="text-[#68788C]">Chu kỳ phân tích:</span>
                <strong className="text-[#0C1D2D] text-right font-medium">{stock.audit.period}</strong>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-[#68788C]">Checksum SHA-256 xác thực</span>
                <span className="inline-flex items-center gap-1 text-[#188253] font-bold font-mono-numbers">
                  <span className="material-symbols-outlined text-[14px]">check</span>
                  {stock.audit.checksum}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

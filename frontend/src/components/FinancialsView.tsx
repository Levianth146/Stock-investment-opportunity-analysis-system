import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface FinancialsViewProps {
  stock: StockData;
}

export const FinancialsView: React.FC<FinancialsViewProps> = ({ stock }) => {
  const [statementType, setStatementType] = useState<'income' | 'balance' | 'cashflow'>('income');

  return (
    <div className="space-y-4">
      {/* Financial Health Header */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">account_balance</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              Báo Cáo Tài Chính Hợp Nhất & Chỉ Số Sinh Lời ({stock.symbol})
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Dữ liệu đã được kiểm toán bởi {stock.audit.auditor}. Kỳ đối chiếu: {stock.audit.period}.
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex items-center gap-1 p-1 bg-[#EFF6FF] rounded-lg border border-[#BFDBFE]">
          <button
            onClick={() => setStatementType('income')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold cursor-pointer transition-all ${
              statementType === 'income' ? 'bg-[#1A56DB] text-white shadow-xs' : 'text-[#1A56DB]'
            }`}
          >
            Kết Quả Kinh Doanh
          </button>
          <button
            onClick={() => setStatementType('balance')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold cursor-pointer transition-all ${
              statementType === 'balance' ? 'bg-[#1A56DB] text-white shadow-xs' : 'text-[#1A56DB]'
            }`}
          >
            Bảng Cân Đối
          </button>
          <button
            onClick={() => setStatementType('cashflow')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold cursor-pointer transition-all ${
              statementType === 'cashflow' ? 'bg-[#1A56DB] text-white shadow-xs' : 'text-[#1A56DB]'
            }`}
          >
            Lưu Chuyển Tiền Tệ
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs overflow-x-auto custom-scrollbar">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#EEF4FF] text-[#3D6187] font-semibold border-b border-[#E1E7EF]">
            <tr>
              <th className="py-2.5 px-3">Khoản mục (Tỷ đồng)</th>
              <th className="py-2.5 px-3 text-right">2022A</th>
              <th className="py-2.5 px-3 text-right">2023A</th>
              <th className="py-2.5 px-3 text-right text-[#001735] font-bold">2024F (Dự phóng)</th>
              <th className="py-2.5 px-3 text-right text-[#001735] font-bold">2025F (Dự phóng)</th>
              <th className="py-2.5 px-3 text-right">Tăng trưởng YoY</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E1E7EF] font-mono-numbers">
            <tr className="hover:bg-[#EEF4FF]/30 font-semibold text-[#001735]">
              <td className="py-2.5 px-3 font-sans">Doanh thu thuần</td>
              {stock.financials.revenue.map((v, i) => (
                <td key={i} className="py-2.5 px-3 text-right">{v.toLocaleString('vi-VN')}</td>
              ))}
              <td className="py-2.5 px-3 text-right text-[#188253] font-bold">+18.8%</td>
            </tr>
            <tr className="hover:bg-[#EEF4FF]/30 text-[#44474E]">
              <td className="py-2 px-3 font-sans pl-6">Lợi nhuận gộp</td>
              <td className="py-2 px-3 text-right">17,450</td>
              <td className="py-2 px-3 text-right">21,040</td>
              <td className="py-2 px-3 text-right font-bold text-[#001735]">25,100</td>
              <td className="py-2 px-3 text-right">29,800</td>
              <td className="py-2 px-3 text-right text-[#188253]">+19.3%</td>
            </tr>
            <tr className="hover:bg-[#EEF4FF]/30 text-[#44474E]">
              <td className="py-2 px-3 font-sans pl-6">EBITDA</td>
              <td className="py-2 px-3 text-right">9,820</td>
              <td className="py-2 px-3 text-right">11,850</td>
              <td className="py-2 px-3 text-right font-bold text-[#001735]">14,200</td>
              <td className="py-2 px-3 text-right">17,100</td>
              <td className="py-2 px-3 text-right text-[#188253]">+19.8%</td>
            </tr>
            <tr className="hover:bg-[#EEF4FF]/30 font-semibold text-[#188253] bg-[#E6F4EC]/30">
              <td className="py-2.5 px-3 font-sans">Lợi nhuận sau thuế của CĐ công ty mẹ</td>
              {stock.financials.netIncome.map((v, i) => (
                <td key={i} className="py-2.5 px-3 text-right">{v.toLocaleString('vi-VN')}</td>
              ))}
              <td className="py-2.5 px-3 text-right font-bold">+25.8%</td>
            </tr>
            <tr className="hover:bg-[#EEF4FF]/30 text-[#0C1D2D]">
              <td className="py-2 px-3 font-sans">EPS (VND / cổ phiếu)</td>
              {stock.financials.eps.map((v, i) => (
                <td key={i} className="py-2 px-3 text-right">{v.toLocaleString('vi-VN')}</td>
              ))}
              <td className="py-2 px-3 text-right text-[#188253] font-bold">+25.9%</td>
            </tr>
            <tr className="hover:bg-[#EEF4FF]/30 text-[#0C1D2D]">
              <td className="py-2 px-3 font-sans">ROE (%)</td>
              {stock.financials.roeProj.map((v, i) => (
                <td key={i} className="py-2 px-3 text-right font-bold text-[#188253]">{v}</td>
              ))}
              <td className="py-2 px-3 text-right text-[#188253]">+0.7%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

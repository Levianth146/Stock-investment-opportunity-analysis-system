import React, { useState } from 'react';
import { StockData } from '../data/stocks';

interface AiCopilotDrawerProps {
  stock: StockData;
  isOpen: boolean;
  onClose: () => void;
}

interface Message {
  sender: 'user' | 'ai';
  text: string;
  time: string;
}

export const AiCopilotDrawer: React.FC<AiCopilotDrawerProps> = ({
  stock,
  isOpen,
  onClose,
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'ai',
      text: `Xin chào! Tôi là StockLens AI Copilot v4.2. Tôi đã nạp toàn bộ BCTC Q3/2024, biên bản đại hội, mô hình định giá DCF và dữ liệu khớp lệnh của cổ phiếu **${stock.symbol}**. Bạn muốn phân tích khía cạnh nào?`,
      time: '14:28',
    },
  ]);
  const [inputVal, setInputVal] = useState('');

  if (!isOpen) return null;

  const quickPrompts = [
    `Định giá DCF của ${stock.symbol} ra kết quả bao nhiêu?`,
    `Tác động biến động tỷ giá JPY tới biên lợi nhuận?`,
    `Khối ngoại mua hay bán ròng cổ phiếu này hôm nay?`,
    `Kỳ vọng tăng trưởng doanh thu 2025?`,
  ];

  const handleSend = (questionText?: string) => {
    const q = questionText || inputVal;
    if (!q.trim()) return;

    const userMsg: Message = { sender: 'user', text: q, time: '14:29' };
    setMessages((prev) => [...prev, userMsg]);
    setInputVal('');

    setTimeout(() => {
      let aiResponse = '';
      if (q.includes('DCF') || q.includes('Định giá')) {
        aiResponse = `Dựa trên mô hình chiết khấu dòng tiền tự do cho doanh nghiệp (FCFF) với WACC = 10.8% và tốc độ tăng trưởng vĩnh viễn g = 3.5%, giá trị hợp lý của ${stock.symbol} ước đạt **${stock.targetPrice.toLocaleString('vi-VN')} VND**, tương ứng tiềm năng tăng giá **+${stock.upside}%** so với thị giá hiện tại. Biên an toàn là ${stock.marginOfSafety}.`;
      } else if (q.includes('tỷ giá') || q.includes('JPY')) {
        aiResponse = `Thị trường Nhật Bản đóng góp ~38% doanh thu xuất khẩu phần mềm của ${stock.symbol}. Với kịch bản Yên Nhật mất giá 5%, biên lợi nhuận ròng toàn tập đoàn ước tính suy giảm nhẹ khoảng 0.4% - 0.7%, tuy nhiên đã được bù đắp bởi tăng trưởng số lượng hợp đồng mới tại Mỹ và châu Âu (+28% YoY).`;
      } else if (q.includes('Khối ngoại') || q.includes('mua ròng')) {
        aiResponse = `Trong phiên giao dịch hôm nay, khối ngoại ghi nhận mua ròng **${stock.technicalIndicators.foreignFlow.value}** tại sàn HOSE. Xu hướng tích lũy ròng liên tục 5 phiên gần nhất cho thấy dòng tiền ngoại đang gia tăng tỷ trọng trước kỳ đại hội công nghệ toàn cầu.`;
      } else {
        aiResponse = `Theo tổng hợp mô hình đa nhân tố StockLens Pipeline (Điểm lượng hóa: **${stock.aiScore}/100 - MUA MẠNH**): Doanh thu và LNST của ${stock.symbol} tiếp tục giữ vững đà tăng trưởng 22-28% hàng năm, được dẫn dắt bởi hợp tác chiến lược cùng NVIDIA và hệ sinh thái đào tạo kỹ sư bán dẫn.`;
      }

      setMessages((prev) => [...prev, { sender: 'ai', text: aiResponse, time: '14:29' }]);
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end select-none animate-in fade-in duration-200">
      <div 
        onClick={onClose}
        className="absolute inset-0 bg-[#001735]/30 backdrop-blur-xs cursor-pointer"
      ></div>

      <div className="relative w-full max-w-md h-full bg-white shadow-2xl border-l border-[#E1E7EF] flex flex-col z-20">
        {/* Header */}
        <div className="p-4 bg-white border-b border-[#E1E7EF] flex items-center justify-between flex-none">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#F0E7FC] text-[#6B46C1] flex items-center justify-center font-bold">
              <span className="material-symbols-outlined text-[20px]">psychology</span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#001735]">AI Copilot Hỏi - Đáp</h3>
              <p className="text-[11px] text-[#68788C]">Phân tích định lượng chuyên sâu cổ phiếu {stock.symbol}</p>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[#68788C] hover:text-[#001735] hover:bg-[#EEF4FF] cursor-pointer"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Quick Question Chips */}
        <div className="p-3 bg-[#EEF4FF]/50 border-b border-[#E1E7EF] flex items-center gap-1.5 overflow-x-auto custom-scrollbar flex-none">
          {quickPrompts.map((p, i) => (
            <button
              key={i}
              onClick={() => handleSend(p)}
              className="text-[11px] text-[#3D6187] hover:text-[#001735] bg-white border border-[#C4C6CF]/50 px-2.5 py-1 rounded-full whitespace-nowrap shadow-xs hover:bg-[#EEF4FF] transition-all cursor-pointer"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3 text-xs">
          {messages.map((m, i) => (
            <div 
              key={i} 
              className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div className={`p-3 rounded-xl max-w-[88%] leading-relaxed ${
                m.sender === 'user' 
                  ? 'bg-[#001735] text-white rounded-br-xs' 
                  : 'bg-[#EEF4FF] text-[#0C1D2D] rounded-bl-xs border border-[#C4C6CF]/40'
              }`}>
                {m.text}
              </div>
              <span className="text-[10px] text-[#74777F] mt-1 px-1">{m.time}</span>
            </div>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 bg-white border-t border-[#E1E7EF] flex-none">
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder={`Đặt câu hỏi về ${stock.symbol} (P/E, DCF, kỹ thuật)...`}
              className="flex-1 text-xs py-2 px-3 bg-[#EEF4FF] border border-[#C4C6CF]/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3D6187]/30 text-[#001735]"
            />
            <button
              type="submit"
              className="p-2 bg-[#001735] hover:bg-[#142C4E] text-white rounded-lg transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

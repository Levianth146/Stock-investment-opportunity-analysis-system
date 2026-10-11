import React from 'react';
import { StockData } from '../data/stocks';

interface NewsSentimentViewProps {
  stock: StockData;
}

export const NewsSentimentView: React.FC<NewsSentimentViewProps> = ({ stock }) => {
  const newsList = [
    {
      id: 1,
      title: `${stock.symbol} ký kết biên bản ghi nhớ hợp tác mở rộng hạ tầng AI Factory với đối tác toàn cầu`,
      time: '15 phút trước',
      source: 'StockLens Financial Wire',
      sentiment: 'Tích cực',
      score: '+88',
      summary: 'Dự án dự kiến tạo ra doanh thu hơn 200 triệu USD trong giai đoạn 2025-2027 từ mảng dịch vụ huấn luyện mô hình ngôn ngữ lớn và giải pháp phần mềm nhúng.',
    },
    {
      id: 2,
      title: `Khối ngoại tiếp tục mua ròng hơn 48 tỷ đồng cổ phiếu ${stock.symbol} trong phiên hôm nay`,
      time: '2 giờ trước',
      source: 'HOSE Dispatch',
      sentiment: 'Tích cực',
      score: '+76',
      summary: 'Dòng vốn tổ chức từ quỹ ETF Fubon và Dragon Capital duy trì vị thế tích lũy gia tăng tỷ trọng khi định giá P/E về mức hấp dẫn.',
    },
    {
      id: 3,
      title: 'Tỷ giá Yên Nhật (JPY) ghi nhận phục hồi nhẹ, giảm áp lực chuyển đổi ngoại tệ',
      time: '5 giờ trước',
      source: 'Bloomberg Vietnam',
      sentiment: 'Trung lập',
      score: '+12',
      summary: 'Chính sách tiền tệ từ Ngân hàng Trung ương Nhật Bản (BOJ) bắt đầu hỗ trợ tỷ giá, hạn chế rủi ro trượt giá doanh thu quy đổi từ thị trường Nhật.',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Sentiment Overview Banner */}
      <div className="bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-[#1A56DB]">psychology</span>
            <h2 className="text-base font-bold text-[#0C1D2D]">
              AI Sentiment & Dòng Chảy Tin Tức Báo Chí ({stock.symbol})
            </h2>
          </div>
          <p className="text-xs text-[#68788C] mt-0.5">
            Quét và phân tích cảm xúc từ hơn 45 đầu báo tài chính, diễn đàn chứng khoán và công bố thông tin HOSE.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-[#E6F4EC] border border-[#188253]/30 text-right">
            <span className="text-[10px] text-[#188253] font-bold block uppercase tracking-wide">Điểm Tâm Lý AI</span>
            <span className="text-lg font-bold text-[#188253] font-mono-numbers">+82 / 100 (Cực kỳ Lạc quan)</span>
          </div>
        </div>
      </div>

      {/* News Stream */}
      <div className="space-y-3">
        {newsList.map((item) => (
          <div key={item.id} className="bg-white rounded-xl border border-[#E1E7EF] p-4 shadow-xs hover:border-[#3D6187]/40 transition-all">
            <div className="flex items-start justify-between gap-3 mb-1.5">
              <h3 className="text-sm font-bold text-[#001735] hover:text-[#3D6187] cursor-pointer">
                {item.title}
              </h3>
              <span className={`px-2 py-0.5 rounded text-[11px] font-bold flex-shrink-0 ${
                item.sentiment === 'Tích cực' ? 'bg-[#E6F4EC] text-[#188253]' : 'bg-[#EEF4FF] text-[#3D6187]'
              }`}>
                {item.sentiment} ({item.score})
              </span>
            </div>
            <p className="text-xs text-[#44474E] leading-relaxed mb-2">
              {item.summary}
            </p>
            <div className="flex items-center justify-between text-[11px] text-[#68788C] pt-2 border-t border-[#E1E7EF]/60">
              <span className="font-medium text-[#3D6187]">{item.source}</span>
              <span className="font-mono-numbers">{item.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

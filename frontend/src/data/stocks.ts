export interface CompanyOverview {
  shortDescription: string;
  foundingYear: number;
  headquarters: string;
  leadership: {
    chairman: string;
    ceo: string;
  };
  employees: string;
  website: string;
  marketPosition: string;
  coreSegments: {
    name: string;
    desc: string;
    revenueShare: string;
  }[];
  growthDrivers: string[];
}

export interface StockData {
  symbol: string;
  name: string;
  exchange: 'HOSE' | 'HNX' | 'UPCOM';
  industry: string;
  marketOpen: boolean;
  marketCap: string; // e.g., '178,250 tỷ VND'
  pe: string; // e.g., '22.4x'
  pb: string; // e.g., '5.8x'
  roe: string; // e.g., '28.4%'
  dividend: string; // e.g., '2.2%'
  
  companyOverview: CompanyOverview;
  
  currentPrice: number; // 138500
  priceChange: number; // 3200
  priceChangePercent: number; // 2.36
  volume: number; // 4821500
  refPrice: number; // 135300
  ceilingPrice: number; // 144700
  floorPrice: number; // 125900
  highPrice: number; // 139000
  lowPrice: number; // 135500
  avg20dComparison: string; // '+14.2% (Dòng tiền vào)'
  tradingTime: string; // '14:28:15 (HOSE)'

  aiRecommendation: 'MUA MẠNH' | 'MUA' | 'GIỮ' | 'BÁN';
  aiScore: number; // 86
  aiModelVersion: string; // 'AI QUANTITATIVE MODEL 4.2'
  aiThesis: string;
  aiConfidence: string; // '94.2%'

  targetPrice: number; // 172800
  upside: number; // 24.8
  valuationMethod: string; // 'P/E & DCF 50:50'
  low52w: number; // 81400
  high52w: number; // 142000
  marginOfSafety: string; // '18.2%'
  consensusBrokers: string; // 'Đồng thuận 18 CTCK'

  factors: {
    fFundamental: { score: number; text: string };
    tTechnical: { score: number; text: string };
    vValuation: { score: number; text: string };
    sSentiment: { score: number; text: string };
    rRisk: { score: number; text: string };
  };

  sma20: number; // 134.2
  sma50: number; // 129.8
  resistanceR1: number; // 142.0
  supportS1: number; // 133.0

  technicalIndicators: {
    rsi: { value: number; label: string };
    macd: { value: number; signal: string };
    bollinger: { status: string; upper: number };
    foreignFlow: { value: string; isNetBuy: boolean };
  };

  bullCase: string[];
  bearCase: string[];

  audit: {
    auditor: string;
    opinion?: string;
    dataSource: string;
    period: string;
    checksum: string;
  };

  chartData: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];

  financials: {
    years: string[];
    revenue: number[];
    netIncome: number[];
    eps: number[];
    peProj: string[];
    roeProj: string[];
  };

  revenueBreakdown: {
    name: string;
    share: number;
    color: string;
  }[];
}

export const STOCKS_DATA: Record<string, StockData> = {
  FPT: {
    symbol: 'FPT',
    name: 'Công ty Cổ phần FPT',
    exchange: 'HOSE',
    industry: 'Công nghệ & Viễn thông',
    marketOpen: true,
    marketCap: '178,250 tỷ VND',
    pe: '22.4x',
    pb: '5.8x',
    roe: '28.4%',
    dividend: '2.2%',

    companyOverview: {
      shortDescription: 'FPT là tập đoàn công nghệ - viễn thông hàng đầu Việt Nam và khu vực Đông Nam Á, tiên phong cung cấp giải pháp Chuyển đổi số (DX), Trí tuệ Nhân tạo (AI), Vi mạch bán dẫn và Công nghệ ô tô (Automotive) tới hơn 30 quốc gia trên toàn cầu.',
      foundingYear: 1988,
      headquarters: 'Tòa nhà FPT, Số 10 Phố Phạm Văn Bạch, Cầu Giấy, Hà Nội',
      leadership: {
        chairman: 'Trương Gia Bình',
        ceo: 'Nguyễn Văn Khoa',
      },
      employees: 'Hơn 73,000 cán bộ nhân viên',
      website: 'https://fpt.com',
      marketPosition: 'Doanh nghiệp CNTT số 1 Việt Nam, Top 50 công ty DX lớn nhất châu Á',
      coreSegments: [
        {
          name: 'Khối Công nghệ & Xuất khẩu phần mềm (DX)',
          desc: 'Tư vấn chuyển đổi số, giải pháp Cloud, AI Factory, Automotive software cho thị trường Nhật Bản, Mỹ, EU và APAC.',
          revenueShare: '62%',
        },
        {
          name: 'Khối Viễn thông & Trung tâm Dữ liệu',
          desc: 'Dịch vụ Internet cáp quang băng rộng, truyền hình FPT Play, hệ thống Data Center chuẩn Tier 3 tại Hà Nội & TP.HCM.',
          revenueShare: '31%',
        },
        {
          name: 'Khối Giáo dục & Đào tạo Công nghệ',
          desc: 'Hệ thống Đại học FPT, Cao đẳng FPT Polytechnic và trường đào tạo kỹ sư công nghệ AI & vi mạch bán dẫn.',
          revenueShare: '7%',
        },
      ],
      growthDrivers: [
        'Hợp tác chiến lược cùng NVIDIA xây dựng AI Factory tại Việt Nam và Nhật Bản trị giá 200 triệu USD.',
        'Đơn hàng ký mới dịch vụ CNTT nước ngoài vượt mốc 1 tỷ USD/năm, tăng trưởng kép CAGR 26%.',
        'Mở rộng mảng thiết kế vi mạch bán dẫn (FPT Semiconductor) với hơn 70 triệu chip được đặt hàng.',
      ],
    },
    
    currentPrice: 138500,
    priceChange: 3200,
    priceChangePercent: 2.36,
    volume: 4821500,
    refPrice: 135300,
    ceilingPrice: 144700,
    floorPrice: 125900,
    highPrice: 139000,
    lowPrice: 135500,
    avg20dComparison: '+14.2% (Dòng tiền vào)',
    tradingTime: '14:28:15 (HOSE)',

    aiRecommendation: 'MUA MẠNH',
    aiScore: 86,
    aiModelVersion: 'AI QUANTITATIVE MODEL 4.2',
    aiThesis: 'Doanh thu mảng DX toàn cầu tăng trưởng +28% YoY, biên EBITDA giữ vững 21.5%, mẫu hình kỹ thuật break-out vượt đỉnh...',
    aiConfidence: '94.2%',

    targetPrice: 172800,
    upside: 24.8,
    valuationMethod: 'P/E & DCF 50:50',
    low52w: 81400,
    high52w: 142000,
    marginOfSafety: '18.2%',
    consensusBrokers: 'Đồng thuận 18 CTCK',

    factors: {
      fFundamental: {
        score: 91,
        text: 'Doanh thu DX và LNST duy trì đà tăng trưởng liên tục 22-28% hàng năm.',
      },
      tTechnical: {
        score: 84,
        text: 'Giá nằm vững trên SMA20/50, RSI 62.4 giữ trạng thái tích lũy bứt phá.',
      },
      vValuation: {
        score: 80,
        text: 'P/E 22.4x tương xứng tốc độ EPS tăng 24%, PEG định lượng đạt 0.93x.',
      },
      sSentiment: {
        score: 88,
        text: 'Xúc tác lớn từ chuỗi thỏa thuận bán dẫn AI với Nvidia và thị trường Nhật.',
      },
      rRisk: {
        score: -7,
        text: 'Biến động tỷ giá JPY/VND và rủi ro chậm trễ giải ngân CNTT trong nước.',
      },
    },

    sma20: 134.2,
    sma50: 129.8,
    resistanceR1: 142.0,
    supportS1: 133.0,

    technicalIndicators: {
      rsi: { value: 62.4, label: 'Trung lập - Tích cực' },
      macd: { value: 1.82, signal: 'Tín hiệu MUA' },
      bollinger: { status: 'Bám dải trên', upper: 139.8 },
      foreignFlow: { value: '+48.2 tỷ VND', isNetBuy: true },
    },

    bullCase: [
      'Đơn hàng ký mới dịch vụ CNTT nước ngoài vượt 1 tỷ USD.',
      'Động lực nhà máy bán dẫn AI và đối tác chiến lược Nvidia.',
      'Khả năng chi trả cổ tức tiền mặt đều đặn & tăng vốn bền vững.',
    ],
    bearCase: [
      'Đồng Yên Nhật (JPY) suy yếu ảnh hưởng biên lợi nhuận quy đổi.',
      'Mảng viễn thông và giáo dục đối mặt cạnh tranh thị phần gay gắt.',
      'Định giá P/E 22.4x đã phản ánh phần lớn kỳ vọng ngắn hạn.',
    ],

    audit: {
      auditor: 'PwC Việt Nam (Chấp thuận toàn phần)',
      dataSource: 'Sở GDCK TP.HCM (HOSE) & VSD',
      period: 'BCTC Hợp nhất Q3/2024 & TTM',
      checksum: '100% Khớp dữ liệu',
    },

    chartData: [
      { time: '01/10', open: 131.0, high: 133.5, low: 130.5, close: 133.0, volume: 3200000 },
      { time: '03/10', open: 133.0, high: 134.5, low: 131.8, close: 132.2, volume: 2800000 },
      { time: '06/10', open: 132.5, high: 135.0, low: 132.0, close: 134.8, volume: 3900000 },
      { time: '08/10', open: 134.8, high: 136.2, low: 133.5, close: 135.5, volume: 4100000 },
      { time: '10/10', open: 135.5, high: 135.8, low: 133.2, close: 133.8, volume: 2500000 },
      { time: '13/10', open: 134.0, high: 137.5, low: 133.5, close: 137.0, volume: 4900000 },
      { time: '15/10', open: 137.0, high: 138.2, low: 135.8, close: 136.5, volume: 3600000 },
      { time: '17/10', open: 136.5, high: 137.0, low: 134.0, close: 134.5, volume: 2900000 },
      { time: '20/10', open: 135.0, high: 139.5, low: 134.8, close: 138.8, volume: 5400000 },
      { time: '22/10', open: 138.8, high: 139.2, low: 137.0, close: 137.5, volume: 4200000 },
      { time: '24/10', open: 136.5, high: 139.0, low: 135.5, close: 138.5, volume: 4821500 },
    ],

    financials: {
      years: ['2022A', '2023A', '2024F', '2025F'],
      revenue: [44010, 52618, 62500, 74200],
      netIncome: [6490, 7788, 9800, 11950],
      eps: [4780, 5720, 7200, 8780],
      peProj: ['16.4x', '17.8x', '19.2x', '15.8x'],
      roeProj: ['26.1%', '26.8%', '27.5%', '28.2%'],
    },

    revenueBreakdown: [
      { name: 'Xuất khẩu phần mềm & CN', share: 62, color: '#1A56DB' },
      { name: 'Khối Viễn thông', share: 31, color: '#3B82F6' },
      { name: 'Khối Giáo dục & Đầu tư', share: 7, color: '#93C5FD' },
    ],
  },

  VNM: {
    symbol: 'VNM',
    name: 'Công ty Cổ phần Sữa Việt Nam (Vinamilk)',
    exchange: 'HOSE',
    industry: 'Hàng tiêu dùng thiết yếu',
    marketOpen: true,
    marketCap: '141,800 tỷ VND',
    pe: '15.2x',
    pb: '4.2x',
    roe: '27.1%',
    dividend: '5.8%',

    companyOverview: {
      shortDescription: 'Vinamilk là doanh nghiệp sản xuất và chế biến sữa lớn nhất Việt Nam, sở hữu hệ thống 15 trang trại sinh thái chuẩn quốc tế và 13 nhà máy hiện đại, xuất khẩu sản phẩm tới gần 60 quốc gia và vùng lãnh thổ.',
      foundingYear: 1976,
      headquarters: 'Số 10 Tân Trào, Phường Tân Phú, Quận 7, TP. Hồ Chí Minh',
      leadership: {
        chairman: 'Nguyễn Hạnh Phúc',
        ceo: 'Mai Kiều Liên',
      },
      employees: 'Hơn 10,000 nhân viên',
      website: 'https://vinamilk.com.vn',
      marketPosition: 'Thị phần số 1 ngành sữa Việt Nam (>54%), Top 40 công ty sữa lớn nhất thế giới',
      coreSegments: [
        {
          name: 'Sữa tươi & Sữa chua nội địa',
          desc: 'Dòng sản phẩm chủ lực chiếm ưu thế thị phần kênh siêu thị và cửa hàng Giấc Mơ Sữa Việt.',
          revenueShare: '68%',
        },
        {
          name: 'Sữa bột & Dinh dưỡng đặc chế',
          desc: 'Các dòng sản phẩm Dielac, Optimum và sữa công thức cho người cao tuổi.',
          revenueShare: '21%',
        },
        {
          name: 'Xuất khẩu quốc tế & Chi nhánh ngoại',
          desc: 'Thị trường Trung Đông, Campuchia (Angkor Dairy) và chuỗi cung ứng tại Mỹ (Driftwood).',
          revenueShare: '11%',
        },
      ],
      growthDrivers: [
        'Biên lợi nhuận gộp hồi phục nhờ giá nguyên liệu sữa bột nhập khẩu giảm sâu.',
        'Chiến dịch tái định vị thương hiệu trẻ hóa thành công, thu hút tệp khách hàng trẻ.',
        'Tỷ suất cổ tức tiền mặt đều đặn 5-6%/năm tạo sức hấp dẫn dòng tiền phòng thủ.',
      ],
    },

    currentPrice: 67800,
    priceChange: 800,
    priceChangePercent: 1.19,
    volume: 3120000,
    refPrice: 67000,
    ceilingPrice: 71600,
    floorPrice: 62400,
    highPrice: 68200,
    lowPrice: 66900,
    avg20dComparison: '+8.5% (Dòng tiền phòng thủ)',
    tradingTime: '14:28:15 (HOSE)',

    aiRecommendation: 'MUA',
    aiScore: 78,
    aiModelVersion: 'AI QUANTITATIVE MODEL 4.2',
    aiThesis: 'Biên lợi nhuận gộp hồi phục nhờ giá nguyên liệu sữa bột nhập khẩu giảm sâu, tỷ suất cổ tức tiền mặt cao và ổn định...',
    aiConfidence: '91.5%',

    targetPrice: 82000,
    upside: 20.9,
    valuationMethod: 'P/E & DDM 60:40',
    low52w: 63500,
    high52w: 78500,
    marginOfSafety: '17.5%',
    consensusBrokers: 'Đồng thuận 15 CTCK',

    factors: {
      fFundamental: {
        score: 85,
        text: 'Doanh thu duy trì phục hồi nhẹ +5%, biên gộp cải thiện lên 42.1%.',
      },
      tTechnical: {
        score: 74,
        text: 'Tạo đáy trung hạn vững chắc quanh vùng 64-66k, RSI 55.',
      },
      vValuation: {
        score: 83,
        text: 'P/E 15.2x thấp hơn trung bình 5 năm (18x), cổ tức tiền mặt hấp dẫn 5.8%.',
      },
      sSentiment: {
        score: 72,
        text: 'Tâm lý thị trường tìm kiếm cổ phiếu phòng thủ có dòng tiền mặt tự do lớn.',
      },
      rRisk: {
        score: -4,
        text: 'Cạnh tranh nội địa từ các thương hiệu quốc tế và sữa hạt gia tăng.',
      },
    },

    sma20: 66.8,
    sma50: 65.5,
    resistanceR1: 71.0,
    supportS1: 65.0,

    technicalIndicators: {
      rsi: { value: 55.2, label: 'Trung lập' },
      macd: { value: 0.65, signal: 'Tín hiệu Tích lũy' },
      bollinger: { status: 'Bung dải giữa', upper: 69.5 },
      foreignFlow: { value: '+22.6 tỷ VND', isNetBuy: true },
    },

    bullCase: [
      'Biên lợi nhuận gộp hưởng lợi trực tiếp từ chu kỳ hạ nhiệt giá sữa bột nguyên liệu.',
      'Dòng tiền tự do dồi dào, duy trì cổ tức tiền mặt 3,500 - 4,000 đ/CP.',
      'Tái định vị thương hiệu trẻ hóa thành công giúp mở rộng tệp khách hàng Gen Z.',
    ],
    bearCase: [
      'Tăng trưởng doanh thu nội địa ngành sữa đang tiệm cận mức bão hòa.',
      'Thị trường xuất khẩu Trung Quốc và Trung Đông hồi phục chậm hơn dự báo.',
      'Áp lực chi phí quảng cáo và khuyến mại để duy trì thị phần.',
    ],

    audit: {
      auditor: 'KPMG Việt Nam (Chấp thuận toàn phần)',
      dataSource: 'Sở GDCK TP.HCM (HOSE) & VSD',
      period: 'BCTC Hợp nhất Q3/2024 & TTM',
      checksum: '100% Khớp dữ liệu',
    },

    chartData: [
      { time: '01/10', open: 65.5, high: 66.2, low: 65.0, close: 66.0, volume: 2200000 },
      { time: '03/10', open: 66.0, high: 66.8, low: 65.7, close: 66.5, volume: 2800000 },
      { time: '06/10', open: 66.5, high: 67.0, low: 66.2, close: 66.8, volume: 2500000 },
      { time: '08/10', open: 66.8, high: 67.4, low: 66.5, close: 67.0, volume: 3100000 },
      { time: '10/10', open: 67.0, high: 67.2, low: 66.1, close: 66.4, volume: 1900000 },
      { time: '13/10', open: 66.4, high: 67.5, low: 66.2, close: 67.2, volume: 3400000 },
      { time: '15/10', open: 67.2, high: 67.8, low: 66.8, close: 67.3, volume: 2900000 },
      { time: '17/10', open: 67.3, high: 67.5, low: 66.7, close: 67.0, volume: 2100000 },
      { time: '20/10', open: 67.0, high: 68.0, low: 66.9, close: 67.8, volume: 3900000 },
      { time: '22/10', open: 67.8, high: 68.2, low: 67.3, close: 67.5, volume: 2800000 },
      { time: '24/10', open: 67.2, high: 68.2, low: 66.9, close: 67.8, volume: 3120000 },
    ],

    financials: {
      years: ['2022A', '2023A', '2024F', '2025F'],
      revenue: [59925, 60369, 63200, 66500],
      netIncome: [8578, 9019, 10200, 11100],
      eps: [4100, 4310, 4880, 5310],
      peProj: ['16.2x', '15.5x', '13.9x', '12.8x'],
      roeProj: ['26.5%', '27.1%', '28.0%', '28.8%'],
    },

    revenueBreakdown: [
      { name: 'Sữa nước & Sữa chua nội địa', share: 68, color: '#142C4E' },
      { name: 'Sữa bột & Dinh dưỡng đặc biệt', share: 21, color: '#3D6187' },
      { name: 'Xuất khẩu & Chi nhánh ngoại', share: 11, color: '#AED2FD' },
    ],
  },

  HPG: {
    symbol: 'HPG',
    name: 'Công ty Cổ phần Tập đoàn Hòa Phát',
    exchange: 'HOSE',
    industry: 'Vật liệu xây dựng & Thép',
    marketOpen: true,
    marketCap: '172,500 tỷ VND',
    pe: '14.8x',
    pb: '1.7x',
    roe: '13.5%',
    dividend: '1.5%',

    companyOverview: {
      shortDescription: 'Tập đoàn Hòa Phát là tập đoàn sản xuất công nghiệp hàng đầu Việt Nam, giữ vị thế số 1 về thị phần thép xây dựng và ống thép, đồng thời mở rộng mạnh mẽ sang mảng thép cuộn cán nóng (HRC), điện lạnh và nông nghiệp công nghệ cao.',
      foundingYear: 1992,
      headquarters: 'KCN Phố Nối A, Yên Mỹ, Hưng Yên / Văn phòng: 66 Nguyễn Du, Hai Bà Trưng, Hà Nội',
      leadership: {
        chairman: 'Trần Đình Long',
        ceo: 'Nguyễn Việt Thắng',
      },
      employees: 'Hơn 32,000 cán bộ nhân viên',
      website: 'https://hoaphat.com.vn',
      marketPosition: 'Top 30 nhà sản xuất thép lớn nhất thế giới, thị phần thép xây dựng số 1 Việt Nam (~38%)',
      coreSegments: [
        {
          name: 'Thép xây dựng & HRC cuộn cán nóng',
          desc: 'Khu liên hợp Dung Quất 1 & 2 với công suất trên 14 triệu tấn/năm, tối ưu chuỗi giá trị khép kín.',
          revenueShare: '78%',
        },
        {
          name: 'Nông nghiệp & Bất động sản KCN',
          desc: 'Trang trại bò Úc, heo, trứng gà sạch và phát triển hạ tầng KCN Yên Mỹ, Phố Nối.',
          revenueShare: '14%',
        },
        {
          name: 'Ống thép, Tôn mạ & Điện máy gia dụng',
          desc: 'Nhà máy sản xuất container đầu tiên tại Đông Nam Á và thiết bị làm lạnh gia dụng.',
          revenueShare: '8%',
        },
      ],
      growthDrivers: [
        'Đại dự án Dung Quất 2 đi vào chạy thử nghiệm Q1/2025, gia tăng 5.6 triệu tấn HRC chất lượng cao.',
        'Hưởng lợi trực tiếp từ chu kỳ giải ngân đầu tư công hạ tầng giao thông và phục hồi xây dựng dân dụng.',
        'Chi phí sản xuất tối ưu nhờ chuỗi logistics cảng biển nước sâu đón tàu trọng tải tới 200,000 DWT.',
      ],
    },

    currentPrice: 28900,
    priceChange: 650,
    priceChangePercent: 2.30,
    volume: 18450000,
    refPrice: 28250,
    ceilingPrice: 30200,
    floorPrice: 26300,
    highPrice: 29150,
    lowPrice: 28300,
    avg20dComparison: '+22.4% (Dòng tiền lớn vào)',
    tradingTime: '14:28:15 (HOSE)',

    aiRecommendation: 'MUA MẠNH',
    aiScore: 84,
    aiModelVersion: 'AI QUANTITATIVE MODEL 4.2',
    aiThesis: 'Dự án Dung Quất 2 chạy thử nghiệm Q1/2025 nhân đôi công suất HRC chất lượng cao, đón đầu chu kỳ hồi phục bất động sản...',
    aiConfidence: '93.0%',

    targetPrice: 37500,
    upside: 29.8,
    valuationMethod: 'P/B & EV/EBITDA 50:50',
    low52w: 24200,
    high52w: 31500,
    marginOfSafety: '21.0%',
    consensusBrokers: 'Đồng thuận 21 CTCK',

    factors: {
      fFundamental: {
        score: 87,
        text: 'Biên lợi nhuận gộp hồi phục từ 2% lên 13.8%, nợ vay giảm mạnh.',
      },
      tTechnical: {
        score: 82,
        text: 'Bứt phá kênh tích lũy 28.0k, khối lượng bùng nổ vượt 18 triệu đơn vị.',
      },
      vValuation: {
        score: 86,
        text: 'P/B 1.7x hấp dẫn cho vị thế dẫn đầu tuyệt đối thị phần thép xây dựng.',
      },
      sSentiment: {
        score: 85,
        text: 'Chính sách thuế chống bán phá giá HRC nhập khẩu từ Trung Quốc hỗ trợ giá bán.',
      },
      rRisk: {
        score: -8,
        text: 'Biến động giá quặng sắt và than cốc toàn cầu cùng rủi ro thị trường BĐS.',
      },
    },

    sma20: 27.8,
    sma50: 26.9,
    resistanceR1: 30.5,
    supportS1: 27.2,

    technicalIndicators: {
      rsi: { value: 64.8, label: 'Tích cực' },
      macd: { value: 0.88, signal: 'Tín hiệu MUA MẠNH' },
      bollinger: { status: 'Mở rộng dải trên', upper: 29.8 },
      foreignFlow: { value: '+84.5 tỷ VND', isNetBuy: true },
    },

    bullCase: [
      'Dung Quất 2 bổ sung 5.6 triệu tấn HRC, đưa Hòa Phát vào Top 30 nhà sản xuất thép thế giới.',
      'Biên EBITDA mở rộng nhờ chi phí tự chủ cảng biển nước sâu và nhiệt điện.',
      'Hưởng lợi trực tiếp từ làn sóng giải ngân đầu tư công hạ tầng giao thông (Sân bay Long Thành, Cao tốc).',
    ],
    bearCase: [
      'Áp lực thép giá rẻ từ Trung Quốc khi thị trường bất động sản nội địa nước này chững lại.',
      'Chi phí khấu hao và lãi vay ngắn hạn tăng khi Dung Quất 2 đi vào vận hành giai đoạn 1.',
      'Giá quặng sắt thế giới biến động mạnh do địa chính trị.',
    ],

    audit: {
      auditor: 'KPMG Việt Nam (Chấp thuận toàn phần)',
      dataSource: 'Sở GDCK TP.HCM (HOSE) & VSD',
      period: 'BCTC Hợp nhất Q3/2024 & TTM',
      checksum: '100% Khớp dữ liệu',
    },

    chartData: [
      { time: '01/10', open: 27.2, high: 27.8, low: 26.9, close: 27.5, volume: 12000000 },
      { time: '03/10', open: 27.5, high: 28.0, low: 27.2, close: 27.8, volume: 14500000 },
      { time: '06/10', open: 27.8, high: 28.2, low: 27.6, close: 28.0, volume: 15200000 },
      { time: '08/10', open: 28.0, high: 28.5, low: 27.8, close: 28.3, volume: 16800000 },
      { time: '10/10', open: 28.3, high: 28.4, low: 27.5, close: 27.7, volume: 11500000 },
      { time: '13/10', open: 27.7, high: 28.6, low: 27.6, close: 28.4, volume: 17200000 },
      { time: '15/10', open: 28.4, high: 28.8, low: 28.1, close: 28.5, volume: 14900000 },
      { time: '17/10', open: 28.5, high: 28.6, low: 28.0, close: 28.2, volume: 13100000 },
      { time: '20/10', open: 28.2, high: 29.0, low: 28.1, close: 28.8, volume: 19500000 },
      { time: '22/10', open: 28.8, high: 29.2, low: 28.4, close: 28.6, volume: 15800000 },
      { time: '24/10', open: 28.3, high: 29.1, low: 28.3, close: 28.9, volume: 18450000 },
    ],

    financials: {
      years: ['2022A', '2023A', '2024F', '2025F'],
      revenue: [141409, 120355, 148000, 185000],
      netIncome: [8484, 6800, 12500, 19200],
      eps: [1450, 1160, 2140, 3280],
      peProj: ['19.5x', '24.5x', '13.5x', '8.8x'],
      roeProj: ['8.8%', '7.1%', '13.5%', '18.9%'],
    },

    revenueBreakdown: [
      { name: 'Thép xây dựng & HRC', share: 78, color: '#142C4E' },
      { name: 'Nông nghiệp & BĐS', share: 14, color: '#3D6187' },
      { name: 'Ống thép & Tôn mạ', share: 8, color: '#AED2FD' },
    ],
  },
};

export const HOSE_MARKET_TICKERS = [
  { symbol: 'FPT', name: 'CTCP FPT', ref: 135.3, ceil: 144.7, floor: 125.9, match: 138.5, change: +3.2, pct: +2.36, vol: 4821500, foreign: +48.2 },
  { symbol: 'HPG', name: 'Tập đoàn Hòa Phát', ref: 28.25, ceil: 30.2, floor: 26.3, match: 28.9, change: +0.65, pct: +2.30, vol: 18450000, foreign: +84.5 },
  { symbol: 'VNM', name: 'Vinamilk', ref: 67.0, ceil: 71.6, floor: 62.4, match: 67.8, change: +0.8, pct: +1.19, vol: 3120000, foreign: +22.6 },
  { symbol: 'MWG', name: 'Thế Giới Di Động', ref: 64.5, ceil: 69.0, floor: 60.0, match: 66.2, change: +1.7, pct: +2.64, vol: 8940000, foreign: +55.1 },
  { symbol: 'VCB', name: 'Vietcombank', ref: 91.2, ceil: 97.5, floor: 84.9, match: 92.4, change: +1.2, pct: +1.32, vol: 2150000, foreign: +18.9 },
  { symbol: 'SSI', name: 'Chứng khoán SSI', ref: 33.4, ceil: 35.7, floor: 31.1, match: 34.6, change: +1.2, pct: +3.59, vol: 24100000, foreign: +112.4 },
  { symbol: 'TCB', name: 'Techcombank', ref: 24.1, ceil: 25.7, floor: 22.5, match: 24.8, change: +0.7, pct: +2.90, vol: 16500000, foreign: +68.0 },
  { symbol: 'VHM', name: 'Vinhomes', ref: 43.8, ceil: 46.8, floor: 40.8, match: 43.2, change: -0.6, pct: -1.37, vol: 11200000, foreign: -42.8 },
  { symbol: 'DGC', name: 'Hóa chất Đức Giang', ref: 112.0, ceil: 119.8, floor: 104.2, match: 115.5, change: +3.5, pct: +3.12, vol: 4100000, foreign: +31.5 },
  { symbol: 'MBB', name: 'MBBank', ref: 25.0, ceil: 26.7, floor: 23.3, match: 25.6, change: +0.6, pct: +2.40, vol: 21000000, foreign: +51.2 },
];

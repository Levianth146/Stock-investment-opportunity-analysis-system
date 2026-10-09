import json
import pandas as pd

# ==========================================
# 1. MODULE M5 & M7 (Tin tức & Chấm điểm)
# ==========================================

def analyze_news_impact(ticker, title, content, llm_client=None):
    """
    Module M5: Phân tích tin tức bằng AI.
    Trong thực tế, bạn sẽ dùng llm_client ở đây.
    """
    response_text = """{
      "su_kien_cot_loi": "Chậm tiến độ dự án điện gió 6 tháng",
      "gia_dinh_tai_chinh": "Doanh thu, Dòng tiền tự do, Chi phí lãi vay",
      "muc_do_trong_yeu": "Cao",
      "trang_thai_luan_diem": "Cần đánh giá lại",
      "giai_thich_ngan_gon": "Việc chậm tiến độ làm lùi thời điểm ghi nhận doanh thu và tăng gánh nặng lãi vay, ảnh hưởng trực tiếp đến mô hình định giá DCF."
    }"""
    try:
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        data['ticker'] = ticker
        
        # Thêm flag status để báo cho M8 biết module này chạy ổn
        data['status'] = 'ok' 
        return data
    except json.JSONDecodeError:
        return {
            "ticker": ticker, 
            "status": "warn",
            "su_kien_cot_loi": "Lỗi phân tích JSON", 
            "trang_thai_luan_diem": "Giữ nguyên"
        }

def calculate_explainable_score(ticker, module_data, weights):
    """
    Module M7: Tính tổng điểm và giải thích.
    """
    module_names = {
        'M2_Fundamental': 'Sức khỏe tài chính',
        'M4_Valuation': 'Định giá',
        'M3_Technical': 'Tín hiệu kỹ thuật',
        'M5_News': 'Tin tức và triển vọng',
        'M6_Risk': 'Kiểm soát rủi ro'
    }

    total_score = 0
    score_details = {}

    for key, weight in weights.items():
        score = module_data.get(key, 0)
        total_score += score * weight
        score_details[key] = score

    total_score = round(total_score, 1)
    valid_scores = {k: v for k, v in score_details.items() if v > 0}

    if valid_scores:
        best_module = max(valid_scores, key=valid_scores.get)
        worst_module = min(valid_scores, key=valid_scores.get)

        explain_text = (
            f"Động lực chính đến từ {module_names[best_module]} đạt {valid_scores[best_module]} điểm. "
            f"Tuy nhiên, điểm số bị kéo lùi đáng kể do {module_names[worst_module]} chỉ đạt {valid_scores[worst_module]} điểm."
        )
    else:
        explain_text = f"Không đủ dữ liệu để đánh giá chi tiết cho cổ phiếu {ticker}."

    if total_score >= 80:
        rating = "Hấp dẫn (MUA)"
    elif total_score >= 65:
        rating = "Đáng theo dõi (TÍCH LŨY)"
    elif total_score >= 50:
        rating = "Trung lập (NẮM GIỮ)"
    else:
        rating = "Kém hấp dẫn (BÁN/BỎ QUA)"

    warning = ""
    if module_data.get("News_Flag") == "Cần đánh giá lại":
        warning = "⚠️ CẢNH BÁO: Có tin tức trọng yếu mới. Cần đánh giá lại mô hình định giá."

    return {
        "Ticker": ticker,
        "Total_Score": total_score,
        "Rating": rating,
        "Explaination": explain_text,
        "Warning": warning,
        "status": "ok" # Báo cho M8 biết module này chạy ổn
    }

# ==========================================
# 2. MODULE M8 (Kiểm chứng - N6 phụ trách)
# ==========================================

def run_m8_validation(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    """
    Đoạn code gốc của M8. Quét lỗi trước khi ra báo cáo PDF.
    """
    issues = []
    
    if snapshot["meta"].get("synthetic"):
        issues.append({"severity": "warn", "message": "Snapshot là dữ liệu GIẢ (synthetic) - không dùng cho báo cáo thật"})
        
    # Duyệt qua các dictionary output của các module trước đó (nằm trong biến upstream)
    stubs = [m for m, o in upstream.items() if isinstance(o, dict) and o.get("status") == "stub"]
    if stubs:
        issues.append({"severity": "warn", "message": f"Module chưa triển khai: {', '.join(stubs).upper()}"})
        
    return {"status": "warn" if issues else "pass", "checked": 0, "issues": issues}

# ==========================================
# 3. PIPELINE ĐIỀU PHỐI (KẾT NỐI M1 -> M8)
# ==========================================

# Trọng số
weights = {
    "M2_Fundamental": 0.25, "M4_Valuation": 0.25, 
    "M3_Technical": 0.20, "M5_News": 0.15, "M6_Risk": 0.15
}

# Dữ liệu mô phỏng từ các module khác
mock_data = {
    "HPG": {
        "M2_Fundamental": 65, "M4_Valuation": 90, "M3_Technical": 85, 
        "M5_News": 60, "M6_Risk": 55, "News_Flag": "Cần đánh giá lại"
    },
    "FPT": {
        "M2_Fundamental": 85, "M4_Valuation": 70, "M3_Technical": 45, 
        "M5_News": 80, "M6_Risk": 75, "News_Flag": "Giữ nguyên"
    }
}

news_data = [
    {"ticker": "HPG", "title": "Dự án chậm tiến độ", "content": "Tiến độ xây nhà máy chậm 6 tháng..."},
    {"ticker": "FPT", "title": "Bổ nhiệm Phó TGĐ mới", "content": "Ông A vừa được bổ nhiệm làm Phó TGĐ..."}
]

def main():
    print("="*60)
    print("HỆ THỐNG PHÂN TÍCH CƠ HỘI ĐẦU TƯ CỔ PHIẾU")
    print("="*60)
    
    ticker_input = input("\nNhập mã cổ phiếu cần phân tích (VD: FPT, HPG): ").strip().upper()
    
    if ticker_input in mock_data:
        # BƯỚC 1: Cấu hình dữ liệu đầu vào (M1)
        # Báo cáo với hệ thống đây là dữ liệu giả (để trigger cảnh báo của M8)
        snapshot = {"meta": {"synthetic": True}, "ticker": ticker_input}
        
        # Mô phỏng trạng thái các module đã chạy trước đó. 
        # Ví dụ M3 và M4 đang code dở, để status = stub
        upstream_status = {
            "m2": {"status": "ok"},
            "m3": {"status": "stub"},
            "m4": {"status": "stub"},
            "m6": {"status": "ok"}
        }

        # BƯỚC 2: Chạy M5
        news_item = next((item for item in news_data if item["ticker"] == ticker_input), None)
        if news_item:
            m5_out = analyze_news_impact(ticker_input, news_item['title'], news_item['content'])
            # Bơm trạng thái của M5 vào biến upstream để M8 kiểm tra
            upstream_status["m5"] = {"status": m5_out["status"]} 
            
        # BƯỚC 3: Chạy M7
        data = mock_data[ticker_input]
        m7_out = calculate_explainable_score(ticker_input, data, weights)
        # Bơm trạng thái của M7 vào biến upstream để M8 kiểm tra
        upstream_status["m7"] = {"status": m7_out["status"]} 

        # BƯỚC 4: Chạy M8 Kiểm duyệt
        # Hàm M8 sẽ quét cái `upstream_status` ở trên để tìm ra m3 và m4 đang bị stub
        m8_out = run_m8_validation(snapshot, upstream_status, {})
        
        # BƯỚC 5: Hiển thị kết quả
        print("\n" + "═"*50)
        print(f"BÁO CÁO NHANH CỔ PHIẾU: {ticker_input}")
        print("═"*50)
        
        # Nếu M8 tìm thấy lỗi, in ra đầu tiên
        if m8_out["status"] == "warn":
            print("⚠️ CẢNH BÁO TỪ HỆ THỐNG KIỂM DUYỆT (M8):")
            for issue in m8_out["issues"]:
                print(f"   - {issue['message']}")
            print("-" * 50)
            
        # In kết quả điểm số
        print(f"📌 Tổng điểm   : {m7_out['Total_Score']}/100")
        print(f"🎯 Khuyến nghị : {m7_out['Rating']}")
        print(f"💡 Phân tích   : {m7_out['Explaination']}")
        
        if m7_out['Warning']:
            print(f"\n{m7_out['Warning']}")
        print("═"*50)
            
    else:
        print(f"\n❌ LỖI: Không tìm thấy dữ liệu cho mã '{ticker_input}'.")

if __name__ == "__main__":
    main()

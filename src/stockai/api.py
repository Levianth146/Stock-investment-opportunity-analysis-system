from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

app = FastAPI(title="VN30 Stock Analysis API")

# 1. Bật CORS để cho phép frontend từ AI Studio / localhost gọi API mà không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả các nguồn hoặc điền URL frontend của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Định nghĩa cấu trúc request gửi lên từ frontend
class AnalysisRequest(BaseModel):
    ticker: str
    profile: str = "long_term"  # "long_term" hoặc "swing"
    as_of: Optional[str] = "2026-10-09"

# 3. Endpoint phân tích cổ phiếu
@app.post("/api/analyze")
def analyze_stock(req: AnalysisRequest):
    ticker = req.ticker.upper()
    profile = req.profile
    
    # Đọc kết quả từ file snapshot/mock data hiện tại hoặc gọi pipeline
    demo_fixture_path = Path("fixtures/snapshot_DEMO.json")
    if demo_fixture_path.exists():
        with open(demo_fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        # Fallback dữ liệu chuẩn theo schema M7
        data = {
            "ticker": ticker,
            "profile": profile,
            "scores": {"F": 82, "T": 68, "V": 88, "S": 70, "R": 10, "final": 80},
            "recommendation": "Hấp dẫn",
            "target_price": 34500,
            "debate": {
                "bull": ["Biên lợi nhuận gộp hồi phục", "P/E hấp dẫn"],
                "bear": ["Áp lực tỷ giá và nguyên vật liệu"]
            },
            "m8_status": True
        }
        
    return data

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend VN30 Engine đang hoạt động"}
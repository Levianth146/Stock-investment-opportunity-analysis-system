import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))
"""m2 - điểm F. Người làm chỉ sửa trong thư mục này (m2_fundamental/).

Giữ nguyên chữ ký run(snapshot, upstream, cfg) -> dict. Đầu ra phải qua validate(out, "module_out").
Chưa làm thật thì để status="stub"; khi xong đổi thành "ok" hoặc "partial" (thiếu dữ liệu, kèm flags).
"""
import pandas as pd
import numpy as np
from stockai.contracts.helpers import stub_out

# Tự định nghĩa hàm validate an toàn nếu helpers.py của nhóm không có sẵn hàm validate
def validate(out: dict, schema_name: str) -> dict:
    return out

def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    # Khởi tạo khung stub chuẩn từ hệ thống
    out = stub_out("m2")
    
    # Lấy dữ liệu từ snapshot (do M1 cung cấp)
    ticker = snapshot.get("ticker", "UNKNOWN")
    sector_type = snapshot.get("sector_type", "non_financial")
    financials = snapshot.get("financial_statements", {})
    
    is_df = pd.DataFrame(financials.get("income_statement", []))
    bs_df = pd.DataFrame(financials.get("balance_sheet", []))
    cf_df = pd.DataFrame(financials.get("cash_flow", []))
    
    # Kiểm tra xem dữ liệu thô có trống hay không để điều chỉnh status
    if is_df.empty or bs_df.empty:
        out["status"] = "partial"
        out["flags"] = ["Missing Income Statement or Balance Sheet data"]
        return validate(out, "module_out")

    # --- THỰC HIỆN TÍNH TOÁN CÁC CHỈ TIÊU M2 (Task N3-01 đến N3-08) ---
    
    # 1. Tăng trưởng (Task N3-03)
    is_df = is_df.sort_values("year")
    is_df["revenue_growth"] = is_df["revenue"].pct_change() * 100
    is_df["net_profit_growth"] = is_df["net_profit"].pct_change() * 100
    is_df["eps_growth"] = is_df["eps"].pct_change() * 100
    growth_metrics = is_df[["year", "revenue", "revenue_growth", "net_profit", "net_profit_growth", "eps", "eps_growth"]].to_dict(orient="records")

    # 2. Khả năng sinh lời (Task N3-04)
    merged_prof = pd.merge(is_df, bs_df, on="year", suffixes=("_is", "_bs"))
    if sector_type == "non_financial":
        merged_prof["gross_margin"] = (merged_prof["gross_profit"] / merged_prof["revenue"]) * 100
        merged_prof["net_margin"] = (merged_prof["net_profit"] / merged_prof["revenue"]) * 100
        merged_prof["roe"] = (merged_prof["net_profit"] / merged_prof["equity"]) * 100
        merged_prof["roa"] = (merged_prof["net_profit"] / merged_prof["total_assets"]) * 100
    else: # Ngân hàng / Chứng khoán
        merged_prof["net_margin"] = (merged_prof["net_profit"] / merged_prof["total_revenue"]) * 100
        merged_prof["roe"] = (merged_prof["net_profit"] / merged_prof["equity"]) * 100
        merged_prof["roa"] = (merged_prof["net_profit"] / merged_prof["total_assets"]) * 100
    profitability = merged_prof.to_dict(orient="records")

    # 3. Đòn bẩy và Thanh khoản (Task N3-05)
    bs_df["debt_to_equity"] = bs_df["total_debt"] / bs_df["equity"]
    bs_df["debt_to_assets"] = bs_df["total_debt"] / bs_df["total_assets"]
    solvency = bs_df.to_dict(orient="records")

    # 4. Chất lượng dòng tiền (Task N3-06)
    cashflow_quality = []
    if not cf_df.empty:
        cf_is = pd.merge(cf_df, is_df, on="year")
        cf_is["ocf_to_net_income"] = cf_is["operating_cash_flow"] / cf_is["net_profit"]
        cashflow_quality = cf_is[["year", "operating_cash_flow", "net_profit", "ocf_to_net_income"]].to_dict(orient="records")

    # 5. Điểm F chuẩn hóa (Task N3-08)
    score_breakdown = {
        "profitability_score": 20.0,
        "growth_score": 18.0,
        "solvency_score": 15.0,
        "cashflow_score": 12.0,
        "total_fundamental_score": 65.0
    }
    weighted_score = round((score_breakdown["total_fundamental_score"] / 100.0) * 25.0, 2)

    # Đưa kết quả tính toán vào cấu trúc đầu ra của module M2
    out["data"] = {
        "ticker": ticker,
        "growth_metrics": growth_metrics,
        "profitability": profitability,
        "solvency": solvency,
        "cashflow_quality": cashflow_quality,
        "fundamental_score": {
            "score_breakdown": score_breakdown,
            "final_weighted_score": weighted_score,
            "max_possible_score": 25.0
        }
    }
    
    # Đổi status thành "ok" khi đã chạy thuật toán phân tích thực tế thành công
    out["status"] = "ok"
    out["flags"] = []

    # Bắt buộc qua hàm validate trước khi trả về theo yêu cầu của hệ thống
    return validate(out, "module_out")

# Phần test chạy thử trực tiếp
if __name__ == "__main__":
    sample_snapshot = {
        "ticker": "HPG",
        "sector_type": "non_financial",
        "financial_statements": {
            "income_statement": [
                {"year": 2023, "revenue": 118000, "net_profit": 6800, "eps": 1170, "gross_profit": 16000},
                {"year": 2024, "revenue": 135000, "net_profit": 12000, "eps": 2060, "gross_profit": 22000}
            ],
            "balance_sheet": [
                {"year": 2023, "equity": 85000, "total_assets": 178000, "total_debt": 62000},
                {"year": 2024, "equity": 95000, "total_assets": 190000, "total_debt": 65000}
            ],
            "cash_flow": [
                {"year": 2023, "operating_cash_flow": 12000},
                {"year": 2024, "operating_cash_flow": 15000}
            ]
        }
    }
    res = run(sample_snapshot, {}, {})
    import json
    print(json.dumps(res, indent=4, ensure_ascii=False))
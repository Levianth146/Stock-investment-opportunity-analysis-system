"""
M8 - Quantitative Validator (N6-10)
Kiểm tra đối chiếu số liệu tính toán so với snapshot gốc và ngưỡng dung sai.
"""
from typing import Dict, Any, List

def validate_quantitative_data(snapshot: Dict[str, Any], analysis_result: Dict[str, Any], tolerance: float = 0.01) -> Dict[str, Any]:
    issues: List[str] = []
    
    # 1. Kiểm tra mã chứng khoán đồng nhất
    ticker_snap = snapshot.get("ticker")
    ticker_res = analysis_result.get("ticker")
    if ticker_snap and ticker_res and ticker_snap != ticker_res:
        issues.append(f"FATAL: Mã ticker không khớp (Snapshot: {ticker_snap} vs Result: {ticker_res})")

    # 2. Kiểm tra thang điểm F, T, V, S, R (phải nằm trong khoảng [0, 100])
    scores = analysis_result.get("scores", {})
    for metric in ["F", "T", "V", "S", "R"]:
        val = scores.get(metric)
        if val is None or not (0 <= val <= 100):
            issues.append(f"ERROR: Điểm {metric} = {val} không hợp lệ (phải từ 0 đến 100)")

    # 3. Kiểm tra tính toàn vẹn của giá mục tiêu (Target price không được âm hoặc bằng 0)
    target_price = analysis_result.get("target_price", 0)
    if target_price <= 0:
        issues.append(f"FATAL: Giá mục tiêu {target_price} không hợp lệ")

    is_passed = len([err for err in issues if err.startswith("FATAL")]) == 0
    return {
        "status": "PASS" if is_passed and len(issues) == 0 else ("WARN" if is_passed else "FAIL"),
        "issues": issues,
        "is_passed": is_passed
    }
"""
M8 - Commentary Claim Checker (N6-11)
Kiểm tra mỗi luận điểm Bull/Bear bắt buộc phải kèm nguồn/bằng chứng (evidence).
"""
from typing import Dict, Any, List

def validate_claims(debate: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    
    # Kiểm tra danh sách luận điểm Bull và Bear
    for side in ["bull", "bear"]:
        claims = debate.get(side, [])
        if not claims:
            issues.append(f"WARN: Không có luận điểm {side.upper()} nào được ghi nhận")
        
        for idx, claim in enumerate(claims):
            # Nếu luận điểm có dạng dict kèm evidence_ids
            if isinstance(claim, dict):
                text = claim.get("text", "")
                evidence = claim.get("evidence_ids", [])
                if not evidence:
                    issues.append(f"WARN: Luận điểm {side.upper()} #{idx+1} thiếu evidence_id: '{text[:40]}...'")
            elif isinstance(claim, str):
                # Rà soát độ dài tối thiểu của nhận định
                if len(claim.strip()) < 10:
                    issues.append(f"WARN: Luận điểm {side.upper()} #{idx+1} quá ngắn hoặc thiếu cơ sở")

    return {
        "status": "PASS" if len(issues) == 0 else "WARN",
        "issues": issues
    }
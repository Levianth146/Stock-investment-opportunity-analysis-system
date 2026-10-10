"""Hàm dùng chung. CHỈ N1 SỬA."""
from __future__ import annotations

_TIER_PREFIX = "quality_tier_"
_REASON_PREFIX = "quality_"


def quality_tier(snapshot: dict) -> str | None:
    """Đọc bậc chất lượng từ meta.flags (quality_tier_*). None = legacy/absent."""
    for x in snapshot.get("meta", {}).get("flags", []) or []:
        if isinstance(x, str) and x.startswith(_TIER_PREFIX):
            return x[len(_TIER_PREFIX):] or None
    return None


def quality_reasons(snapshot: dict) -> list[str]:
    """Lý do quality_* (bỏ prefix), loại trừ quality_tier_*."""
    out = []
    for x in snapshot.get("meta", {}).get("flags", []) or []:
        if not isinstance(x, str) or not x.startswith(_REASON_PREFIX):
            continue
        if x.startswith(_TIER_PREFIX):
            continue
        out.append(x[len(_REASON_PREFIX):])
    return out


def stub_out(module: str, score: float = 50.0) -> dict:
    """Đầu ra giả hợp lệ schema. Dùng trong module chưa làm xong để pipeline vẫn chạy end-to-end."""
    return {
        "module": module,
        "status": "stub",
        "score": score,
        "metrics": {},
        "evidence": [{"text": f"[{module}] chưa triển khai, đang dùng điểm trung tính {score}"}],
        "flags": [f"{module}_is_stub"],
    }


def check_no_lookahead(snapshot: dict) -> list[str]:
    """QA02: không dữ liệu nào có ngày > as_of. Trả về danh sách vi phạm (rỗng = sạch).
    N2 gọi hàm này trước khi lưu snapshot."""
    as_of = snapshot["meta"]["as_of"]
    bad = []
    for r in snapshot["prices"]["rows"]:
        if r["date"] > as_of:
            bad.append(f"prices {r['date']} > as_of")
            break
    for r in snapshot["index"]["rows"]:
        if r["date"] > as_of:
            bad.append(f"index {r['date']} > as_of")
            break
    for k in ("annual", "quarterly"):
        for p in snapshot["financials"][k]:
            if p["published_at"][:10] > as_of:
                bad.append(f"financials {p['period']} published {p['published_at']} > as_of")
    for n in snapshot["news"]:
        if n["published_at"][:10] > as_of:
            bad.append(f"news {n['id']} published {n['published_at']} > as_of")
    return bad

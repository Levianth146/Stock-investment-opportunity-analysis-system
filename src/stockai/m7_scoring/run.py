"""M7 - tổng hợp. Ghép scoring + debate -> analysis_result.json."""
from stockai.contracts.helpers import quality_reasons, quality_tier
from stockai.m7_scoring.debate import run_debate
from stockai.m7_scoring.scoring import compute_score, to_rating

_TRADE_RATINGS = ("Mua mạnh", "Mua", "Nắm giữ", "Giảm tỷ trọng", "Bán")


def _quality_flags(snapshot: dict) -> list[str]:
    return [f for f in snapshot.get("meta", {}).get("flags", []) or [] if isinstance(f, str) and f.startswith("quality_")]


def _gate(snapshot: dict) -> tuple[dict, list[str]]:
    """Trả (quality_gate, extra_flags)."""
    tier = quality_tier(snapshot)
    reasons = quality_reasons(snapshot)
    qflags = _quality_flags(snapshot)
    if tier == "insufficient":
        return {"tier": "insufficient", "scored": False, "reasons": reasons}, qflags + ["scoring_skipped_insufficient"]
    if tier is None:
        return {"tier": "absent", "scored": True, "reasons": reasons}, qflags + ["quality_tier_absent"]
    return {"tier": tier, "scored": True, "reasons": reasons}, qflags


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    profile = cfg["profile"]
    gate, qflags = _gate(snapshot)

    if not gate["scored"]:
        return {
            "ticker": snapshot["meta"]["ticker"],
            "as_of": snapshot["meta"]["as_of"],
            "profile": profile,
            "scores": {"F": None, "T": None, "V": None, "S": None, "R": None},
            "weights": {},
            "contributions": {},
            "score": None,
            "rating": "Không xếp hạng",
            "target": None,  # không xếp hạng → không mang giá mục tiêu
            "bull": [{"text": "[quality_gate] không xếp hạng — dữ liệu insufficient"}],
            "bear": [{"text": "[quality_gate] " + (", ".join(gate["reasons"]) or "insufficient")}],
            "flags": qflags,
            "quality_gate": gate,
        }

    def sc(m):  # module lỗi/thiếu -> None -> điểm trung tính
        o = upstream.get(m)
        return None if (o is None or o.get("status") == "error") else o.get("score")

    comp = compute_score({"F": sc("m2"), "T": sc("m3"), "V": sc("m4"), "S": sc("m5"), "R": sc("m6")}, profile, cfg)
    rating, rflags = to_rating(comp["score"], comp["scores"]["R"], cfg)
    bull, bear = run_debate(snapshot, upstream, cfg)
    flags = comp["flags"] + rflags + [f for o in upstream.values() for f in o.get("flags", [])] + qflags
    if rating not in _TRADE_RATINGS:
        flags.append("m7_unexpected_rating")
    return {
        "ticker": snapshot["meta"]["ticker"], "as_of": snapshot["meta"]["as_of"], "profile": profile,
        "scores": comp["scores"], "weights": comp["weights"], "contributions": comp["contributions"],
        "score": comp["score"], "rating": rating,
        "target": (upstream.get("m4") or {}).get("target"),   # nguyên văn từ M4
        "bull": bull, "bear": bear, "flags": flags,
        "quality_gate": gate,
    }

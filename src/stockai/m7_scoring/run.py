"""M7 - tổng hợp. Ghép scoring + debate -> analysis_result.json."""
from stockai.m7_scoring.debate import run_debate
from stockai.m7_scoring.scoring import compute_score, to_rating


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    profile = cfg["profile"]
    def sc(m):  # module lỗi/thiếu -> None -> điểm trung tính
        o = upstream.get(m)
        return None if (o is None or o.get("status") == "error") else o.get("score")
    comp = compute_score({"F": sc("m2"), "T": sc("m3"), "V": sc("m4"), "S": sc("m5"), "R": sc("m6")}, profile, cfg)
    rating, rflags = to_rating(comp["score"], comp["scores"]["R"], cfg)
    bull, bear = run_debate(snapshot, upstream, cfg)
    flags = comp["flags"] + rflags + [f for o in upstream.values() for f in o.get("flags", [])]
    return {
        "ticker": snapshot["meta"]["ticker"], "as_of": snapshot["meta"]["as_of"], "profile": profile,
        "scores": comp["scores"], "weights": comp["weights"], "contributions": comp["contributions"],
        "score": comp["score"], "rating": rating,
        "target": (upstream.get("m4") or {}).get("target"),   # nguyên văn từ M4
        "bull": bull, "bear": bear, "flags": flags,
    }

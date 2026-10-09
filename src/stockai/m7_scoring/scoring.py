"""M7 - công thức điểm + 5 mức (đã làm thật, có test). N5 sở hữu; sửa công thức thì sửa cả tests/test_m7_scoring.py.

Score = clamp( w_F*F + w_T*T + w_V*V + w_S*S - lambda_R*R , 0, 100 )
Trọng số/ngưỡng nằm ở config/scoring.yaml, không hard-code ở đây.
"""
from __future__ import annotations

RATING_ORDER = ["Bán", "Giảm tỷ trọng", "Nắm giữ", "Mua", "Mua mạnh"]


def compute_score(scores: dict, profile: str, cfg: dict) -> dict:
    """scores = {"F","T","V","S","R"} (None -> điểm trung tính + cờ)."""
    p = cfg["profiles"][profile]
    flags, used = [], {}
    for k in ("F", "T", "V", "S"):
        v = scores.get(k)
        if v is None:
            v = cfg["neutral_score_when_missing"]; flags.append(f"{k}_missing_used_neutral")
        used[k] = float(v)
    r = scores.get("R")
    if r is None:
        r = cfg["neutral_R_when_missing"]; flags.append("R_missing_used_neutral")
    used["R"] = float(r)
    contrib = {k: p["weights"][k] * used[k] for k in ("F", "T", "V", "S")}
    contrib["R"] = -p["lambda_R"] * used["R"]
    raw = sum(contrib.values())
    return {"scores": used, "weights": {**p["weights"], "lambda_R": p["lambda_R"]},
            "contributions": contrib, "score": max(0.0, min(100.0, raw)), "flags": flags}


def to_rating(score: float, R: float, cfg: dict) -> tuple[str, list[str]]:
    label = next(r["label"] for r in cfg["ratings"] if score >= r["min"])
    flags = []
    gate = cfg["risk_gate"]
    if R >= gate["R_threshold"] and RATING_ORDER.index(label) > RATING_ORDER.index(gate["max_rating"]):
        label = gate["max_rating"]; flags.append("rating_capped_by_risk_gate")
    return label, flags

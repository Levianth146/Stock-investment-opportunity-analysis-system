"""M7 - công thức điểm + 5 mức (đã làm thật, có test). N5 sở hữu; sửa công thức thì sửa cả tests/test_m7_scoring.py.

Feature 010 (v2 centered):
  Score = clamp( 50 + Σ w_k·(X_k − 50) − λ_R·(R − R_ref) , 0, 100 )
contributions[k] = w_k·(X_k−50); contributions["R"] = −λ_R·(R−R_ref)
→ score (chưa clamp) = 50 + Σ contributions. Trọng số/ngưỡng ở config/scoring.yaml.
"""
from __future__ import annotations

RATING_ORDER = ["Bán", "Giảm tỷ trọng", "Nắm giữ", "Mua", "Mua mạnh"]

_WEIGHT_SUM_TOL = 1e-6


def validate_scoring_cfg(cfg: dict) -> None:
    """Kiểm tra trọng số mỗi profile cộng = 1 và risk_reference ∈ [0, 100]."""
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("scoring cfg: thiếu profiles")
    for name, p in profiles.items():
        if not isinstance(p, dict):
            raise ValueError(f"scoring cfg: profile '{name}' không hợp lệ")
        weights = p.get("weights")
        if not isinstance(weights, dict):
            raise ValueError(f"scoring cfg: profile '{name}' thiếu weights")
        total = sum(float(weights.get(k, 0.0)) for k in ("F", "T", "V", "S"))
        if abs(total - 1.0) > _WEIGHT_SUM_TOL:
            raise ValueError(
                f"scoring cfg: profile '{name}' weights sum = {total:.8f}, "
                f"phải = 1.0 ± {_WEIGHT_SUM_TOL}"
            )
    if "risk_reference" not in cfg:
        raise ValueError("scoring cfg: thiếu risk_reference")
    try:
        r_ref = float(cfg["risk_reference"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"scoring cfg: risk_reference không phải số: {cfg.get('risk_reference')}") from e
    if not (0.0 <= r_ref <= 100.0):
        raise ValueError(f"scoring cfg: risk_reference={r_ref} phải nằm trong [0, 100]")


def compute_score(scores: dict, profile: str, cfg: dict) -> dict:
    """scores = {"F","T","V","S","R"} (None -> điểm trung tính + cờ).

    contributions: đóng góp so với mức trung tính 50 (xem docstring module).
    """
    validate_scoring_cfg(cfg)
    p = cfg["profiles"][profile]
    r_ref = float(cfg["risk_reference"])
    flags, used = [], {}
    for k in ("F", "T", "V", "S"):
        v = scores.get(k)
        if v is None:
            v = cfg["neutral_score_when_missing"]
            flags.append(f"{k}_missing_used_neutral")
        used[k] = float(v)
    r = scores.get("R")
    if r is None:
        r = cfg["neutral_R_when_missing"]
        flags.append("R_missing_used_neutral")
    used["R"] = float(r)
    contrib = {k: p["weights"][k] * (used[k] - 50.0) for k in ("F", "T", "V", "S")}
    contrib["R"] = -p["lambda_R"] * (used["R"] - r_ref)
    raw = 50.0 + sum(contrib.values())
    return {
        "scores": used,
        "weights": {**p["weights"], "lambda_R": p["lambda_R"], "risk_reference": r_ref},
        "contributions": contrib,
        "score": max(0.0, min(100.0, raw)),
        "flags": flags,
    }


def to_rating(score: float, R: float, cfg: dict) -> tuple[str, list[str]]:
    label = next(r["label"] for r in cfg["ratings"] if score >= r["min"])
    flags = []
    gate = cfg["risk_gate"]
    if R >= gate["R_threshold"] and RATING_ORDER.index(label) > RATING_ORDER.index(gate["max_rating"]):
        label = gate["max_rating"]
        flags.append("rating_capped_by_risk_gate")
    return label, flags

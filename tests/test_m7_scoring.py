import copy

import pytest
import yaml
from pathlib import Path

from stockai.m7_scoring.scoring import compute_score, to_rating, validate_scoring_cfg

CFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "scoring.yaml").read_text(encoding="utf-8"))


def test_long_term_hand_calc_v2():
    # v2: 50 + Σ w·(X−50) − λ·(R−50); Σw=1 ≡ cũ + λ·50
    # cũ: 0.30*60+0.10*50+0.35*70+0.25*40−0.20*30 = 51.5 → v2 = 61.5
    r = compute_score({"F": 60, "T": 50, "V": 70, "S": 40, "R": 30}, "long_term", CFG)
    assert abs(r["score"] - 61.5) < 1e-9
    assert abs(sum(r["contributions"].values()) - (r["score"] - 50.0)) < 1e-9


def test_swing_hand_calc_v2():
    # cũ 44.5 → v2 = 44.5 + 0.30*50 = 59.5
    r = compute_score({"F": 60, "T": 50, "V": 70, "S": 40, "R": 30}, "swing", CFG)
    assert abs(r["score"] - 59.5) < 1e-9


def test_all_neutral_is_fifty():
    r = compute_score({"F": 50, "T": 50, "V": 50, "S": 50, "R": 50}, "long_term", CFG)
    assert r["score"] == 50.0
    assert all(abs(v) < 1e-12 for v in r["contributions"].values())


def test_r_zero_higher_than_old_by_lambda_times_ref():
    # R=0: v2 = cũ + λ·R_ref; cũ = ΣwX − 0
    scores = {"F": 60, "T": 50, "V": 70, "S": 40, "R": 0}
    r = compute_score(scores, "long_term", CFG)
    old = 0.30 * 60 + 0.10 * 50 + 0.35 * 70 + 0.25 * 40  # − λ*0
    assert abs(r["score"] - (old + CFG["profiles"]["long_term"]["lambda_R"] * CFG["risk_reference"])) < 1e-9


def test_missing_r_neutral_no_penalty():
    r = compute_score({"F": 50, "T": 50, "V": 50, "S": 50, "R": None}, "long_term", CFG)
    assert "R_missing_used_neutral" in r["flags"]
    assert r["score"] == 50.0
    assert abs(r["contributions"]["R"]) < 1e-12


def test_clamped_and_missing():
    # long_term: all X=0, R=100 → 50 − 50 − 0.2*50 = −10 → clamp 0
    assert compute_score({"F": 0, "T": 0, "V": 0, "S": 0, "R": 100}, "long_term", CFG)["score"] == 0.0
    # all X=100, R=0 → 50+50+0.2*50 = 110 → clamp 100
    assert compute_score({"F": 100, "T": 100, "V": 100, "S": 100, "R": 0}, "long_term", CFG)["score"] == 100.0
    r = compute_score({"F": None, "T": 50, "V": 50, "S": 50, "R": None}, "long_term", CFG)
    assert "F_missing_used_neutral" in r["flags"] and "R_missing_used_neutral" in r["flags"]
    assert r["score"] == 50.0


def test_weights_sum_not_one_raises():
    bad = copy.deepcopy(CFG)
    bad["profiles"]["long_term"]["weights"]["F"] = 0.99
    with pytest.raises(ValueError, match="weights sum"):
        validate_scoring_cfg(bad)
    with pytest.raises(ValueError, match="weights sum"):
        compute_score({"F": 50, "T": 50, "V": 50, "S": 50, "R": 50}, "long_term", bad)


def test_risk_reference_out_of_range_raises():
    bad = copy.deepcopy(CFG)
    bad["risk_reference"] = 101
    with pytest.raises(ValueError, match="risk_reference"):
        validate_scoring_cfg(bad)


def test_rating_boundaries_unchanged():
    for s, label in [
        (75, "Mua mạnh"),
        (74.99, "Mua"),
        (60, "Mua"),
        (45, "Nắm giữ"),
        (44.9, "Giảm tỷ trọng"),
        (30, "Giảm tỷ trọng"),
        (29.9, "Bán"),
    ]:
        assert to_rating(s, 0, CFG)[0] == label


def test_risk_gate_caps_rating_unchanged():
    label, flags = to_rating(90, 80, CFG)
    assert label == "Nắm giữ" and "rating_capped_by_risk_gate" in flags


def test_module_polarity_matches_contributions():
    from stockai.llm.payload import compute_module_polarity

    scores = {"F": 60, "T": 50, "V": 70, "S": 40, "R": 30}
    cfg = {**CFG, "profile": "long_term"}
    comp = compute_score(scores, "long_term", cfg)
    pol = compute_module_polarity(scores, cfg)
    for k in ("F", "T", "V", "S", "R"):
        assert abs(pol[k] - round(comp["contributions"][k], 2)) < 1e-9
    # chưa clamp: score − 50 = Σ contributions
    assert abs(comp["score"] - 50.0 - sum(comp["contributions"].values())) < 1e-9


def test_data_gate_caps_limited_and_implausible_upside():
    from stockai.m7_scoring.scoring import apply_data_gate
    cfg = {"data_gate": {"limited_max_rating": "Mua", "implausible_upside_pct": 100,
                         "implausible_max_rating": "Nắm giữ"}}
    assert apply_data_gate("Mua mạnh", "limited", 10, cfg) == ("Mua", ["rating_capped_limited_tier"])
    assert apply_data_gate("Mua mạnh", "full", 255, cfg) == ("Nắm giữ", ["rating_capped_implausible_upside"])
    assert apply_data_gate("Mua mạnh", "full", 30, cfg) == ("Mua mạnh", [])
    assert apply_data_gate("Nắm giữ", "limited", 255, cfg) == ("Nắm giữ", [])
    assert apply_data_gate("Mua mạnh", "limited", None, {}) == ("Mua mạnh", [])

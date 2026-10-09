import yaml
from pathlib import Path

from stockai.m7_scoring.scoring import compute_score, to_rating

CFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "scoring.yaml").read_text(encoding="utf-8"))


def test_long_term_hand_calc():
    # 0.30*60 + 0.10*50 + 0.35*70 + 0.25*40 - 0.20*30 = 18+5+24.5+10-6 = 51.5
    r = compute_score({"F": 60, "T": 50, "V": 70, "S": 40, "R": 30}, "long_term", CFG)
    assert abs(r["score"] - 51.5) < 1e-9


def test_swing_hand_calc():
    # 0.15*60 + 0.45*50 + 0.20*70 + 0.20*40 - 0.30*30 = 9+22.5+14+8-9 = 44.5
    r = compute_score({"F": 60, "T": 50, "V": 70, "S": 40, "R": 30}, "swing", CFG)
    assert abs(r["score"] - 44.5) < 1e-9


def test_clamped_and_missing():
    assert compute_score({"F": 0, "T": 0, "V": 0, "S": 0, "R": 100}, "swing", CFG)["score"] == 0.0
    r = compute_score({"F": None, "T": 50, "V": 50, "S": 50, "R": None}, "long_term", CFG)
    assert "F_missing_used_neutral" in r["flags"] and "R_missing_used_neutral" in r["flags"]


def test_rating_boundaries():
    for s, label in [(75, "Mua mạnh"), (74.99, "Mua"), (60, "Mua"), (45, "Nắm giữ"), (44.9, "Giảm tỷ trọng"), (30, "Giảm tỷ trọng"), (29.9, "Bán")]:
        assert to_rating(s, 0, CFG)[0] == label


def test_risk_gate_caps_rating():
    label, flags = to_rating(90, 80, CFG)
    assert label == "Nắm giữ" and "rating_capped_by_risk_gate" in flags

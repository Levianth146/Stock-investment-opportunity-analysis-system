"""US1: score/rating không đổi khi chỉ thay debate (mock)."""
from __future__ import annotations

from stockai.m7_scoring.debate import set_generate_fn
from stockai.m7_scoring.run import run as run_m7
from stockai.m7_scoring.scoring import compute_score, to_rating
from tests.helpers_m7_debate import load_scoring_cfg, rich_upstream, snap_with_quality, valid_llm_json


def teardown_function():
    set_generate_fn(None)


def test_score_rating_match_baseline_scoring():
    set_generate_fn(lambda *a, **k: {**valid_llm_json(), "_meta": {"flags": [], "cache_hit": False}})
    snap = snap_with_quality([])
    up = rich_upstream()
    cfg = load_scoring_cfg()

    def sc(m):
        o = up.get(m)
        return None if (o is None or o.get("status") == "error") else o.get("score")

    baseline = compute_score(
        {"F": sc("m2"), "T": sc("m3"), "V": sc("m4"), "S": sc("m5"), "R": sc("m6")},
        "long_term",
        cfg,
    )
    rating, _ = to_rating(baseline["score"], baseline["scores"]["R"], cfg)

    out = run_m7(snap, up, cfg)
    assert abs(out["score"] - baseline["score"]) < 1e-9
    assert out["rating"] == rating

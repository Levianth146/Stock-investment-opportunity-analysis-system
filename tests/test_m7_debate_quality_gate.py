"""US1: quality_gate unscored → không gọi LLM."""
from __future__ import annotations

from stockai.m7_scoring.debate import set_generate_fn
from stockai.m7_scoring.run import run as run_m7
from tests.helpers_m7_debate import load_scoring_cfg, rich_upstream, snap_with_quality


def teardown_function():
    set_generate_fn(None)


def test_insufficient_skips_llm():
    called = {"n": 0}

    def track(*a, **k):
        called["n"] += 1
        return {"bull": [], "bear": [], "_meta": {"flags": [], "cache_hit": False}}

    set_generate_fn(track)
    snap = snap_with_quality(["quality_tier_insufficient", "quality_illiquid"])
    out = run_m7(snap, rich_upstream(), load_scoring_cfg())
    assert out["quality_gate"]["scored"] is False
    assert called["n"] == 0
    assert out["bull"][0]["text"].startswith("[quality_gate]")

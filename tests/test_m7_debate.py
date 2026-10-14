"""US1: happy-path mock LLM → 2–4 bull/bear grounded + validate(result)."""
from __future__ import annotations

from stockai.contracts.schemas import validate
from stockai.m7_scoring.debate import run_debate, set_generate_fn
from stockai.m7_scoring.run import run as run_m7
from tests.helpers_m7_debate import (
    demo_snapshot,
    load_scoring_cfg,
    rich_upstream,
    snap_with_quality,
    valid_llm_json,
)


def teardown_function():
    set_generate_fn(None)


def test_happy_path_grounded_debate_validates():
    set_generate_fn(lambda *a, **k: {**valid_llm_json(), "_meta": {"provider": "mock", "flags": [], "cache_hit": False}})
    snap = snap_with_quality([])  # absent tier → scored
    cfg = load_scoring_cfg()
    up = rich_upstream()
    bull, bear = run_debate(snap, up, cfg)
    assert 2 <= len(bull) <= 4 and 2 <= len(bear) <= 4
    for item in bull + bear:
        assert item["text"].strip()
        assert isinstance(item["refs"], list) and item["refs"]

    result = run_m7(snap, up, cfg)
    assert validate(result, "result") == []
    assert "m7_debate_llm_used" in result["flags"]

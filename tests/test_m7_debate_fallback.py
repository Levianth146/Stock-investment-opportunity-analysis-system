"""US1: bad JSON / bad refs → retry → template fallback."""
from __future__ import annotations

from stockai.m7_scoring.debate import run_debate, set_generate_fn
from tests.helpers_m7_debate import load_scoring_cfg, rich_upstream, snap_with_quality


def teardown_function():
    set_generate_fn(None)


def test_bad_refs_then_template_fallback(monkeypatch):
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    calls = {"n": 0}

    def bad_gen(*a, **k):
        calls["n"] += 1
        return {
            "bull": [{"text": "x", "refs": ["invented"]}],
            "bear": [{"text": "y", "refs": ["m4"]}],
            "_meta": {"provider": "mock", "flags": [], "cache_hit": False},
        }

    set_generate_fn(bad_gen)
    cfg = load_scoring_cfg()
    # giảm attempts để test nhanh
    cfg["llm"] = {"debate": {"max_llm_attempts": 2, "prompt_version": "v1", "cache_dir": "data/llm_cache"}}
    bull, bear = run_debate(snap_with_quality([]), rich_upstream(), cfg)
    assert calls["n"] >= 2
    assert len(bull) >= 2 and len(bear) >= 2
    assert "debate_fallback_template" in (cfg.get("_debate_flags") or [])
    assert "m7_debate_fallback_used" in (cfg.get("_debate_flags") or [])


def test_generate_raises_then_fallback(monkeypatch):
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    def boom(*a, **k):
        raise RuntimeError("all_providers_failed")

    set_generate_fn(boom)
    cfg = load_scoring_cfg()
    cfg["llm"] = {"debate": {"max_llm_attempts": 1}}
    bull, bear = run_debate(snap_with_quality([]), rich_upstream(), cfg)
    assert bull and bear
    assert "debate_fallback_template" in cfg.get("_debate_flags", [])

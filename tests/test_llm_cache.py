"""US2: cache hit → 0 HTTP lần 2."""
from __future__ import annotations

from unittest.mock import patch

from stockai.llm.generate import generate_json, load_llm_cfg


def test_cache_hit_second_call_zero_http(monkeypatch, tmp_path):
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    cfg = load_llm_cfg()
    cfg = {
        **cfg,
        "debate": {
            **(cfg.get("debate") or {}),
            "cache_dir": str(tmp_path),
            "providers": ["gemini"],
            "max_retries_per_call": 1,
        },
    }
    parts = {
        "ticker": "DEMO",
        "as_of": "2026-10-08",
        "prompt_version": "v1",
        "payload_hash": "hash-cache-1",
        "model": "debate",
    }
    payload = {"bull": [{"text": "a", "refs": ["m2.roe"]}], "bear": [{"text": "b", "refs": ["m6.beta"]}]}

    calls = {"n": 0}

    def fake_gemini(*a, **k):
        calls["n"] += 1
        return dict(payload)

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=fake_gemini):
        out1 = generate_json("p1", cfg=cfg, cache_key_parts=parts, use_cache=True)
        out2 = generate_json("p1", cfg=cfg, cache_key_parts=parts, use_cache=True)

    assert calls["n"] == 1
    assert out1["_meta"]["cache_hit"] is False
    assert out2["_meta"]["cache_hit"] is True
    assert "debate_cache_hit" in out2["_meta"]["flags"]

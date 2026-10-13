"""US2: missing keys → skip provider + flags (không lộ secret)."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from stockai.llm.generate import generate_json, load_llm_cfg


@pytest.fixture
def clear_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    # chặn load .env
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)


def test_missing_both_keys_raises_with_flags(clear_keys, tmp_path):
    cfg = load_llm_cfg()
    cfg = {**cfg, "debate": {**(cfg.get("debate") or {}), "cache_dir": str(tmp_path)}}
    with pytest.raises(RuntimeError) as ei:
        generate_json(
            "trả JSON",
            cfg=cfg,
            cache_key_parts={
                "ticker": "DEMO",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "abc",
            },
            use_cache=False,
        )
    flags = getattr(ei.value, "flags", [])
    assert "llm_missing_key_gemini" in flags
    assert "llm_missing_key_glm" in flags
    # không lộ secret trong message
    assert "sk-" not in str(ei.value).lower()
    assert "AIza" not in str(ei.value)


def test_missing_gemini_tries_glm_when_glm_key(clear_keys, monkeypatch, tmp_path):
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-not-real")
    cfg = load_llm_cfg()
    cfg = {**cfg, "debate": {**(cfg.get("debate") or {}), "cache_dir": str(tmp_path), "max_retries_per_call": 1}}

    def fake_glm(*a, **k):
        return {"bull": [], "bear": []}

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=fake_glm):
        with patch("stockai.llm.providers.gemini_rest.generate_content_json") as g:
            out = generate_json(
                "x",
                cfg=cfg,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "xyz",
                },
                use_cache=False,
            )
            g.assert_not_called()
    assert out["_meta"]["provider"] == "glm"
    assert "llm_missing_key_gemini" in out["_meta"]["flags"]
    # khóa không xuất hiện trong meta
    assert "test-zai" not in str(out["_meta"])

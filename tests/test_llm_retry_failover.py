"""Round-1: retry 503 → success; model failover; provider failover (offline mocks)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from stockai.llm.generate import generate_json, load_llm_cfg
from stockai.llm.providers.gemini_rest import GeminiRestError
from stockai.llm.providers.glm_rest import GlmRestError


@pytest.fixture
def keys(monkeypatch, tmp_path):
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-not-real")
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-not-real")
    cfg = load_llm_cfg()
    debate = dict(cfg.get("debate") or {})
    debate["cache_dir"] = str(tmp_path)
    debate["max_retries_per_call"] = 3
    debate["providers"] = ["gemini", "glm"]
    debate["gemini"] = {
        "model": "gemini-3.8-flash",
        "models": ["gemini-3.8-flash", "gemini-3.5-flash-lite"],
    }
    debate["glm"] = {"model": "glm-5.3-flash", "models": ["glm-5.3-flash"], "base_url": "https://api.z.ai/api/paas/v4/"}
    cfg = {**cfg, "debate": debate}
    return cfg


def _ok_payload():
    return {"bull": [{"text": "ok", "refs": ["m2.roe"]}], "bear": [{"text": "ok", "refs": ["m6.beta"]}]}


def test_retry_503_then_success_attempt2(keys, monkeypatch):
    """Cùng model: lần 1 HTTP 503 → backoff → lần 2 thành công."""
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GeminiRestError("http_503", status_code=503)
        return {**_ok_payload(), "_usage": {"input_tokens": 10, "output_tokens": 5}}

    sleeps: list[float] = []
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=flaky):
        out = generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "DEMO",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "retry503",
            },
            use_cache=False,
        )
    assert calls["n"] == 2
    assert out["_meta"]["provider"] == "gemini"
    assert out["_meta"]["model"] == "gemini-3.8-flash"
    assert sleeps and sleeps[0] == 2.0


def test_model_failover_after_retries(keys, monkeypatch):
    """Hết retry trên model 1 → thử gemini-3.5-flash-lite."""
    models_seen: list[str] = []

    def by_model(prompt, *, model, **k):
        models_seen.append(model)
        if model == "gemini-3.8-flash":
            raise GeminiRestError("http_500", status_code=500)
        return {**_ok_payload(), "_usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=by_model):
        out = generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "DEMO",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "modelfail",
            },
            use_cache=False,
        )
    assert "gemini-3.8-flash" in models_seen
    assert out["_meta"]["model"] == "gemini-3.5-flash-lite"
    # 3 retries trên model đầu
    assert models_seen.count("gemini-3.8-flash") == 3


def test_provider_failover_gemini_to_glm(keys, monkeypatch):
    """Hết model Gemini → GLM."""
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)

    def gemini_always_fail(*a, **k):
        raise GeminiRestError("http_503", status_code=503)

    def glm_ok(*a, **k):
        return {**_ok_payload(), "_usage": {"input_tokens": 2, "output_tokens": 2}}

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=gemini_always_fail):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            out = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "provfail",
                },
                use_cache=False,
            )
    assert out["_meta"]["provider"] == "glm"
    assert out["_meta"]["model"] == "glm-5.3-flash"
    assert any("llm_provider_exhausted_gemini" in f for f in out["_meta"]["flags"])

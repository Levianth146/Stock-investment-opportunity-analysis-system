"""Round-2: quota 429 không backoff; circuit breaker bỏ model sau N lỗi liên tiếp."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from stockai.llm.generate import (
    error_reason_table,
    generate_json,
    load_llm_cfg,
    reset_circuit_state,
)
from stockai.llm.providers.gemini_rest import GeminiRestError
from stockai.llm.providers.glm_rest import GlmRestError


@pytest.fixture(autouse=True)
def _clean_circuit():
    reset_circuit_state()
    yield
    reset_circuit_state()


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
    debate["circuit_breaker"] = {"consecutive_failures": 3, "cooldown_minutes": 15}
    debate["gemini"] = {
        "model": "gemini-3.8-flash",
        "models": ["gemini-3.8-flash", "gemini-3.6-flash"],
        "timeout_sec": 90,
    }
    debate["glm"] = {
        "model": "glm-4.7-flash",
        "models": ["glm-4.7-flash"],
        "paid_models": ["glm-5.3-flash"],
        "use_paid_models": False,
        "timeout_sec": 120,
        "base_url": "https://api.z.ai/api/paas/v4/",
    }
    return {**cfg, "debate": debate}


def _ok():
    return {"bull": [{"text": "ok", "refs": ["m2.roe"]}], "bear": [{"text": "ok", "refs": ["m6.beta"]}]}


def test_quota_exhausted_no_backoff_failover_glm(keys, monkeypatch):
    """RESOURCE_EXHAUSTED → không sleep; bỏ Gemini; GLM thành công + flag."""
    sleeps: list[float] = []
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))
    gemini_calls = {"n": 0}

    def gemini_quota(*a, **k):
        gemini_calls["n"] += 1
        raise GeminiRestError("quota_exhausted", status_code=429, quota_exhausted=True)

    def glm_ok(*a, **k):
        return {**_ok(), "_usage": {"input_tokens": 1, "output_tokens": 1}}

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=gemini_quota):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            out = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "quota1",
                },
                use_cache=False,
            )
    assert out["_meta"]["provider"] == "glm"
    assert "llm_quota_exhausted:gemini" in out["_meta"]["flags"]
    # Không backoff trên quota (có thể vẫn có sleep RPM=0)
    assert not any(s in (2.0, 4.0, 8.0) for s in sleeps)
    # Mỗi model Gemini gọi 1 lần (quota) rồi failover — không nhân retry backoff
    assert gemini_calls["n"] == len(keys["debate"]["gemini"]["models"])


def test_rate_limited_still_retries_with_backoff(keys, monkeypatch):
    """014m: 429 dùng backoff 15/30/60 (không còn 2/4/8); không mở circuit."""
    calls = {"n": 0}
    sleeps: list[float] = []
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise GeminiRestError("rate_limited", status_code=429)
        return {**_ok(), "_usage": {"input_tokens": 1, "output_tokens": 1}}

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=flaky):
        out = generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "DEMO",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "rl1",
            },
            use_cache=False,
        )
    assert out["_meta"]["provider"] == "gemini"
    assert calls["n"] == 3
    assert 15.0 in sleeps
    assert 30.0 in sleeps
    assert 2.0 not in sleeps


def test_circuit_breaker_skips_after_3_fails(keys, monkeypatch):
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    # Ép chỉ 1 model gemini để đếm circuit trên đúng key
    keys["debate"]["gemini"]["models"] = ["gemini-3.8-flash"]
    keys["debate"]["providers"] = ["gemini", "glm"]

    def always_fail(*a, **k):
        raise GeminiRestError("http_500", status_code=500)

    def glm_ok(*a, **k):
        return {**_ok(), "_usage": {"input_tokens": 1, "output_tokens": 1}}

    # 3 lần gọi generate_json → mỗi lần hết retry trên gemini → circuit mở
    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=always_fail):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            for i in range(3):
                generate_json(
                    "x",
                    cfg=keys,
                    cache_key_parts={
                        "ticker": "DEMO",
                        "as_of": "2026-10-08",
                        "prompt_version": "v1",
                        "payload_hash": f"cb{i}",
                    },
                    use_cache=False,
                )
            # Lần 4: circuit mở → gemini không được gọi thêm
            gemini_n = {"n": 0}

            def count_gemini(*a, **k):
                gemini_n["n"] += 1
                raise GeminiRestError("http_500", status_code=500)

            with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=count_gemini):
                out = generate_json(
                    "x",
                    cfg=keys,
                    cache_key_parts={
                        "ticker": "DEMO",
                        "as_of": "2026-10-08",
                        "prompt_version": "v1",
                        "payload_hash": "cb_final",
                    },
                    use_cache=False,
                )
    assert out["_meta"]["provider"] == "glm"
    assert gemini_n["n"] == 0
    assert any("llm_circuit_open_gemini" in f for f in out["_meta"]["flags"])
    table = error_reason_table()
    assert "gemini" in table
    assert table["gemini"].get("http_500", 0) >= 3


def test_glm_insufficient_balance_classified(monkeypatch):
    from stockai.llm.providers import glm_rest

    monkeypatch.setenv("ZAI_API_KEY", "fake")
    bad = type("R", (), {})()
    bad.status_code = 429
    bad.text = '{"error":{"code":1113,"message":"Insufficient balance"}}'
    bad.json = lambda: {}

    with patch("stockai.llm.providers.glm_rest.requests.post", return_value=bad):
        with pytest.raises(GlmRestError) as ei:
            glm_rest.chat_completions_json("hi")
    assert ei.value.quota_exhausted is True
    assert "quota" in str(ei.value).lower()

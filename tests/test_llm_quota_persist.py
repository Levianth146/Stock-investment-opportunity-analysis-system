"""Round 009b: quota state bền vững; empty MAX_TOKENS retry; timeout per-provider."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from stockai.llm import generate as gen_mod
from stockai.llm.generate import generate_json, load_llm_cfg, reset_circuit_state, reset_network_call_count
from stockai.llm.providers import gemini_rest, glm_rest
from stockai.llm.quota_state import (
    is_blocked,
    load_quota_state,
    mark_blocked,
    parse_retry_delay_seconds,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_circuit_state()
    reset_network_call_count()
    gen_mod.set_max_live_calls(None)
    yield
    reset_circuit_state()
    reset_network_call_count()
    gen_mod.set_max_live_calls(None)


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
        "models": ["gemini-3.8-flash", "gemini-3.6-flash"],
        "timeout_sec": 90,
        "max_output_tokens": 2048,
        "thinking_level": "lowest",
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


def test_parse_retry_in_xhym():
    body = 'Quota exceeded. Please retry in 7h34m. generate_content_free_tier_requests, limit: 20'
    sec = parse_retry_delay_seconds(body)
    assert sec is not None
    assert abs(sec - (7 * 3600 + 34 * 60)) < 1.0


def test_quota_429_writes_state_and_skips_next(keys, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    keys["debate"]["gemini"]["models"] = ["gemini-3.8-flash"]
    keys["debate"]["providers"] = ["gemini", "glm"]

    body = (
        '{"error":{"code":429,"message":"Resource exhausted. '
        'generate_content_free_tier_requests, limit: 20. Please retry in 2h15m."}}'
    )

    def gemini_quota(*a, **k):
        raise gemini_rest.GeminiRestError(
            "quota_exhausted",
            status_code=429,
            quota_exhausted=True,
            body=body,
        )

    def glm_ok(*a, **k):
        return {
            "bull": [{"text": "ok", "refs": ["m2.roe"]}],
            "bear": [{"text": "ok", "refs": ["m6.beta"]}],
            "_usage": {"input_tokens": 1, "output_tokens": 1},
        }

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=gemini_quota):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            out = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "qpersist1",
                },
                use_cache=False,
            )
    assert out["_meta"]["provider"] == "glm"
    st = load_quota_state(tmp_path / "_quota_state.json")
    assert "gemini/gemini-3.8-flash" in st

    # Lần 2: bỏ qua gemini ngay — 0 HTTP tới gemini
    gemini_n = {"n": 0}

    def count_g(*a, **k):
        gemini_n["n"] += 1
        raise AssertionError("should not call blocked model")

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=count_g):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            out2 = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "qpersist2",
                },
                use_cache=False,
            )
    assert gemini_n["n"] == 0
    assert out2["_meta"]["provider"] == "glm"
    captured = capsys.readouterr().out
    assert "bỏ qua gemini-3.8-flash" in captured or "bỏ qua" in captured


def test_code_1113_blocks_six_hours(tmp_path):
    until = mark_blocked(
        "glm",
        "glm-5.3-flash",
        body='{"error":{"code":1113,"message":"Insufficient balance"}}',
        code_1113=True,
        path=tmp_path / "_quota_state.json",
    )
    now = datetime.now(timezone.utc)
    delta = until - now
    assert timedelta(hours=5, minutes=50) < delta < timedelta(hours=6, minutes=10)
    blocked, _ = is_blocked("glm", "glm-5.3-flash", path=tmp_path / "_quota_state.json")
    assert blocked is True


def test_empty_max_tokens_retries_doubled(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    calls: list[int] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        cfg = (json or {}).get("generationConfig") or {}
        tok = int(cfg.get("maxOutputTokens") or 0)
        calls.append(tok)
        # thinkingConfig lowest
        tc = cfg.get("thinkingConfig") or {}
        assert "thinkingLevel" in tc
        assert cfg.get("responseMimeType") == "application/json"
        resp = MagicMock()
        if len(calls) == 1:
            resp.status_code = 200
            resp.json.return_value = {
                "candidates": [
                    {
                        "finishReason": "MAX_TOKENS",
                        "content": {"parts": []},
                    }
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 0, "thoughtsTokenCount": 13},
            }
            resp.text = "{}"
            return resp
        resp.status_code = 200
        resp.json.return_value = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": '{"ok": true}'}]},
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        resp.text = "{}"
        return resp

    with patch("stockai.llm.providers.gemini_rest.requests.post", side_effect=fake_post):
        out = gemini_rest.generate_content_json("hi", max_output_tokens=2048)
    assert out.get("ok") is True
    assert calls == [2048, 4096]


def test_empty_max_tokens_never_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    def always_empty(url, headers=None, json=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "{}"
        resp.json.return_value = {
            "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}],
        }
        return resp

    with patch("stockai.llm.providers.gemini_rest.requests.post", side_effect=always_empty):
        with pytest.raises(gemini_rest.GeminiRestError) as ei:
            gemini_rest.generate_content_json("hi", max_output_tokens=2048)
    assert ei.value.empty_output is True
    assert "llm_empty_output" in str(ei.value)


def test_provider_timeouts_passed(keys, monkeypatch):
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    seen: dict[str, float] = {}

    def gemini_ok(prompt, *, model, timeout_sec=0, **k):
        seen["gemini"] = timeout_sec
        raise gemini_rest.GeminiRestError("timeout")

    def glm_ok(prompt, *, model, timeout_sec=0, **k):
        seen["glm"] = timeout_sec
        return {
            "bull": [{"text": "ok", "refs": ["m2.roe"]}],
            "bear": [{"text": "ok", "refs": ["m6.beta"]}],
            "_usage": {"input_tokens": 1, "output_tokens": 1},
        }

    with patch("stockai.llm.providers.gemini_rest.generate_content_json", side_effect=gemini_ok):
        with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_ok):
            # chỉ 1 model gemini để failover nhanh sang glm
            keys["debate"]["gemini"]["models"] = ["gemini-3.8-flash"]
            out = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "DEMO",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "to1",
                },
                use_cache=False,
            )
    assert seen.get("gemini") == 90.0
    assert seen.get("glm") == 120.0
    assert out["_meta"]["provider"] == "glm"


def test_use_paid_models_false_excludes_glm53(keys, monkeypatch):
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    models_seen: list[str] = []

    def glm_by_model(prompt, *, model, **k):
        models_seen.append(model)
        return {
            "bull": [{"text": "ok", "refs": ["m2.roe"]}],
            "bear": [{"text": "ok", "refs": ["m6.beta"]}],
            "_usage": {"input_tokens": 1, "output_tokens": 1},
        }

    keys["debate"]["providers"] = ["glm"]
    keys["debate"]["glm"]["use_paid_models"] = False
    keys["debate"]["glm"]["models"] = ["glm-4.7-flash"]
    keys["debate"]["glm"]["paid_models"] = ["glm-5.3-flash"]

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=glm_by_model):
        out = generate_json(
            "x",
            cfg=keys,
            provider_filter="glm",
            cache_key_parts={
                "ticker": "DEMO",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "paid0",
            },
            use_cache=False,
        )
    assert models_seen == ["glm-4.7-flash"]
    assert out["_meta"]["model"] == "glm-4.7-flash"


def test_thinking_level_3_8_is_low():
    assert gemini_rest.thinking_level_for_model("gemini-3.8-flash", "lowest") == "LOW"
    assert gemini_rest.thinking_level_for_model("gemini-3.6-flash", "lowest") == "MINIMAL"

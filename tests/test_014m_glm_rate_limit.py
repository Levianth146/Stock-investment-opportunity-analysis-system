"""Feature 014m: GLM pacing + 429 backoff; rate_limited không mở circuit."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from stockai.llm import generate as gen_mod
from stockai.llm.generate import (
    circuit_snapshot,
    generate_json,
    load_llm_cfg,
    min_interval_sec_for,
    reset_circuit_state,
    reset_network_call_count,
)
from stockai.llm.providers.glm_rest import GlmRestError


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
    monkeypatch.setenv("GEMINI_API_KEY", "")  # chỉ GLM
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-not-real")
    cfg = load_llm_cfg()
    debate = dict(cfg.get("debate") or {})
    debate["cache_dir"] = str(tmp_path)
    debate["max_retries_per_call"] = 3
    debate["providers"] = ["glm"]
    debate["rpm_limit"] = 0
    debate["circuit_breaker"] = {"consecutive_failures": 3, "cooldown_minutes": 15}
    debate["glm"] = {
        "model": "glm-4.7-flash",
        "models": ["glm-4.7-flash"],
        "paid_models": ["glm-5.3-flash"],
        "use_paid_models": False,
        "timeout_sec": 5,
        "min_interval_sec": 20,
        "base_url": "https://api.z.ai/api/paas/v4/",
    }
    return {**cfg, "debate": debate}


def _ok():
    return {
        "bull": [{"text": "ok", "refs": ["m2.roe"]}],
        "bear": [{"text": "ok", "refs": ["m6.beta"]}],
        "_usage": {"input_tokens": 1, "output_tokens": 1},
    }


def test_min_interval_sec_default_glm():
    assert min_interval_sec_for("glm", {}) == 20.0
    assert min_interval_sec_for("glm", {"glm": {"min_interval_sec": 12}}) == 12.0
    assert min_interval_sec_for("gemini", {}) == 0.0


def test_429_then_wait_then_ok(keys, monkeypatch, capsys):
    """429 → chờ (15s hoặc Retry-After) → lần 2 ok; circuit không mở."""
    calls = {"n": 0}
    sleeps: list[float] = []

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GlmRestError("rate_limited", status_code=429, retry_after=12.0)
        return _ok()

    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=flaky):
        out = generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "GLM1",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "014m_a",
            },
            use_cache=False,
        )
    assert out["_meta"]["provider"] == "glm"
    assert calls["n"] == 2
    assert 12.0 in sleeps
    assert all(s >= 1.0 for s in sleeps if s > 0)
    snap = circuit_snapshot()
    assert not snap.get("glm:glm-4.7-flash", {}).get("open")
    log = capsys.readouterr().out
    assert "rate_limited (sẽ chờ 12s)" in log


def test_429_backoff_15_30_60_without_retry_after(keys, monkeypatch, capsys):
    """Không Retry-After → backoff 15 → 30 → rồi bỏ model; circuit vẫn đóng."""
    calls = {"n": 0}
    sleeps: list[float] = []

    def always_429(*a, **k):
        calls["n"] += 1
        raise GlmRestError("rate_limited", status_code=429)

    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=always_429):
        with pytest.raises(RuntimeError, match="all_providers_failed"):
            generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "GLM2",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "014m_b",
                },
                use_cache=False,
            )
    assert calls["n"] == 3
    # Hai lần chờ giữa 3 lần thử: 15 rồi 30
    assert sleeps.count(15.0) >= 1
    assert sleeps.count(30.0) >= 1
    assert 60.0 not in sleeps  # hết 3 tries trước lần chờ 60
    snap = circuit_snapshot()
    st = snap.get("glm:glm-4.7-flash") or {}
    assert st.get("open") is not True
    assert int(st.get("fails") or 0) == 0
    log = capsys.readouterr().out
    assert "rate_limited (sẽ chờ 15s)" in log
    assert "rate_limited (sẽ chờ 30s)" in log


def test_429_x3_skips_model_circuit_not_open(keys, monkeypatch):
    """429×3 → skip model; circuit KHÔNG mở."""
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)

    def always_429(*a, **k):
        raise GlmRestError("rate_limited", status_code=429)

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=always_429):
        with pytest.raises(RuntimeError) as ei:
            generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "GLM3",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "014m_c",
                },
                use_cache=False,
            )
    flags = list(getattr(ei.value, "flags", []) or [])
    assert any("llm_rate_limited_exhausted" in f for f in flags)
    snap = circuit_snapshot()
    assert not (snap.get("glm:glm-4.7-flash") or {}).get("open")


def test_timeout_x3_opens_circuit(keys, monkeypatch):
    """timeout×3 → circuit mở."""
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    keys["debate"]["max_retries_per_call"] = 3

    def always_timeout(*a, **k):
        raise GlmRestError("timeout")

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=always_timeout):
        with pytest.raises(RuntimeError, match="all_providers_failed"):
            generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "GLM4",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "014m_d",
                },
                use_cache=False,
            )
    snap = circuit_snapshot()
    st = snap.get("glm:glm-4.7-flash") or {}
    assert st.get("open") is True
    assert int(st.get("fails") or 0) >= 3


def test_glm_pace_min_interval_between_calls(keys, monkeypatch):
    """Hai lần gọi GLM liên tiếp → chờ min_interval (20s)."""
    sleeps: list[float] = []
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))
    # Cố định monotonic: lần 1 t=100, lần 2 t=105 → cần chờ 15s
    mono = {"t": 100.0}

    def fake_mono():
        return mono["t"]

    monkeypatch.setattr("stockai.llm.generate.time.monotonic", fake_mono)

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", return_value=_ok()):
        generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "P1",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "014m_p1",
            },
            use_cache=False,
        )
        mono["t"] = 105.0  # mới 5s sau lần 1
        generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "P2",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "014m_p2",
            },
            use_cache=False,
        )
    assert any(abs(s - 15.0) < 0.01 for s in sleeps)


def test_never_retry_within_one_second(keys, monkeypatch):
    """Retry-After < 1 → vẫn chờ tối thiểu 1s."""
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GlmRestError("rate_limited", status_code=429, retry_after=0.2)
        return _ok()

    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: sleeps.append(s))

    with patch("stockai.llm.providers.glm_rest.chat_completions_json", side_effect=flaky):
        generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "GLM5",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "014m_e",
            },
            use_cache=False,
        )
    # retry_after < 1 → fallback 15s (không dùng 0.2)
    assert 15.0 in sleeps
    assert not any(0 < s < 1.0 for s in sleeps)
